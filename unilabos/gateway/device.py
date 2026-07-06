"""
设备工作器 - 把任意 Python 驱动包装成 asyncio 协程。

每个 DeviceWorker:
- 周期性轮询驱动的属性，变化时通过 send_fn 发送 device_status
- 接收 execute_action 调用，将动作派发到驱动方法（同步阻塞调用走线程池）

驱动约定（最小集，等价于现有 @device 装饰器的子集）：
- 属性 = Python @property 或普通字段，read 操作必须是非阻塞或快返回
- 动作 = Python 方法（同步即可，会被 run_in_executor 调度）
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


SendFn = Callable[[Dict[str, Any]], Awaitable[None]]


class DeviceWorker:
    """单个设备的协程工作器。"""

    def __init__(
        self,
        device_id: str,
        driver: Any,
        properties: List[str],
        send_fn: SendFn,
        poll_interval: float = 1.0,
        machine_name: str = "gateway",
        report_unchanged: bool = False,
        property_timeout: float = 5.0,
        action_timeout: float = 60.0,
        driver_factory: Optional[Callable[[], Any]] = None,
        reconnect_threshold: int = 3,
        on_device_lost: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.device_id = device_id
        self.driver = driver
        self.properties = list(properties)
        self.send_fn = send_fn
        self.poll_interval = poll_interval
        self.machine_name = machine_name
        # True: 每个轮询周期都上报；False: 仅值变化时上报，节省带宽
        self.report_unchanged = report_unchanged
        # 超时保护：避免驱动卡在串口阻塞读时拖死整个 telemetry 循环
        self.property_timeout = property_timeout
        # 单次动作执行最长时间（initialize/移动等可能需要几十秒，所以默认更大）
        self.action_timeout = action_timeout
        # 重连工厂：USB 热拔后重新创建驱动实例（重新 open 串口）
        # 不传则不会自动重连，只会持续告警
        self.driver_factory = driver_factory
        # 连续多少次 IO 错误后触发重连（默认 3 次 ≈ 5-10 秒）
        self.reconnect_threshold = reconnect_threshold
        # 设备彻底丢失时的回调（USB 拔出后放弃重连，通知 gateway 移除该 worker）
        self.on_device_lost = on_device_lost

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_values: Dict[str, Any] = {}
        # 每个 property 连续超时多少次后告警一次（避免日志刷屏）
        self._consecutive_errors: Dict[str, int] = {}
        # 串口/USB IO 错误连续计数（跨所有 property 共享，因为通常一损俱损）
        self._io_error_count: int = 0
        # 防止并发重连：同一时刻只有一个 reconnect 协程
        self._reconnecting: bool = False
        # 专用单线程 executor：telemetry（property 读取）走 _driver_executor，
        # action（驱动方法调用）走 _action_executor。两者必须分开:
        # - 共用一个 executor 时，长时间 action（如 start_stir(duration=10) 内部
        #   time.sleep(10)）会霸占 worker，telemetry 排队等→读不到温度/转速。
        # - 分开后 action 阻塞不影响 telemetry；串口物理互斥仍由 driver 自己的
        #   threading.Lock 兜底（典型驱动只在真正写/读串口时持锁，sleep 不持锁）。
        # 每个仍然是单线程 + 可丢弃重建——保留"stuck 时整体丢"的稳定性策略。
        self._driver_executor: Optional[ThreadPoolExecutor] = None
        self._action_executor: Optional[ThreadPoolExecutor] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._telemetry_loop(), name=f"telemetry-{self.device_id}")
        logger.info(
            f"[DEV] {self.device_id} 启动 properties={self.properties} interval={self.poll_interval}s"
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # 释放两个 executor，stuck 的线程让它自己慢慢死
        self._drop_driver_executor()
        self._drop_action_executor()

    async def _telemetry_loop(self) -> None:
        while self._running:
            for prop in self.properties:
                try:
                    value = await self._read_property_async(prop)
                except asyncio.TimeoutError:
                    # 串口阻塞 / 设备没回应——不卡死循环，跳过这次
                    self._consecutive_errors[prop] = self._consecutive_errors.get(prop, 0) + 1
                    n_prop = self._consecutive_errors[prop]
                    # 同时累计全局 IO 错误，因为"读不到任何字节"和"fd 失效"
                    # 在故障表现上等价（典型：设备断电再上电后，driver 缓存了旧的串口
                    # 状态/地址，只有重建驱动才能让 RunzeSyringePump.__init__ 重新走
                    # "open serial + reset_input_buffer" 的初始化流程）。
                    self._io_error_count += 1
                    n_io = self._io_error_count
                    if n_prop in (1, 5, 25, 100) or n_prop % 200 == 0:
                        logger.warning(
                            f"[DEV] 读取 {self.device_id}.{prop} 超时（>{self.property_timeout}s），"
                            f"已连续 {n_prop} 次。检查设备电源/接线/波特率"
                        )
                    # 超时阈值用更宽松的次数（默认 reconnect_threshold * 3 ≈ 10 次 ≈ 50s），
                    # 因为偶发超时不一定是设备出问题，但持续超时几乎肯定需要重建驱动
                    if (
                        n_io >= self.reconnect_threshold * 3
                        and self.driver_factory is not None
                        and not self._reconnecting
                    ):
                        asyncio.create_task(self._try_reconnect())
                    continue
                except Exception as e:
                    is_io = _is_io_error(e)
                    self._io_error_count += 1
                    n = self._io_error_count
                    # 在关键阈值告警，避免疯狂刷日志：1, 3, 10, 30, 100 ...
                    if n in (1, self.reconnect_threshold, 10, 30, 100) or n % 200 == 0:
                        tag = "IO 错误" if is_io else "读取异常"
                        logger.warning(
                            f"[DEV] {self.device_id}.{prop} {tag}（连续 {n} 次）: "
                            f"{type(e).__name__}: {e}"
                        )
                    # 任意类型的连续失败都触发重连：
                    # - OSError/伪 IO：直接走重连
                    # - 其他异常：累计到阈值（同 reconnect_threshold）也走重连，
                    #   因为驱动状态坏了，重建是最稳妥的恢复手段
                    if (
                        n >= self.reconnect_threshold
                        and self.driver_factory is not None
                        and not self._reconnecting
                    ):
                        asyncio.create_task(self._try_reconnect())
                    # 这次循环跳过剩余 property（一损俱损）
                    break

                # 读成功就清错误计数
                if prop in self._consecutive_errors:
                    n = self._consecutive_errors.pop(prop)
                    if n >= 5:
                        logger.info(f"[DEV] {self.device_id}.{prop} 已恢复（之前连续失败 {n} 次）")
                # 任何 property 读成功都清 IO 错误计数（说明串口活了）
                if self._io_error_count > 0:
                    logger.info(
                        f"[DEV] {self.device_id} 串口已恢复（之前连续失败 {self._io_error_count} 次）"
                    )
                    self._io_error_count = 0

                last = self._last_values.get(prop, _SENTINEL)
                if self.report_unchanged or value != last:
                    changed = "" if last is _SENTINEL else f" (was {last!r})"
                    logger.info(f"[DEV] {self.device_id} {prop} = {value!r}{changed}")
                    self._last_values[prop] = value
                    await self.send_fn(
                        {
                            "action": "device_status",
                            "data": {
                                "device_id": self.device_id,
                                "data": {
                                    "property_name": prop,
                                    "status": value,
                                    "timestamp": time.time(),
                                },
                            },
                        }
                    )

            await asyncio.sleep(self.poll_interval)

    def _ensure_driver_executor(self) -> ThreadPoolExecutor:
        """惰性创建专用单线程池。重连时会被 shutdown 并置 None，下次调用会重建。"""
        if self._driver_executor is None:
            self._driver_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=f"driver-{self.device_id}",
            )
        return self._driver_executor

    def _drop_driver_executor(self) -> None:
        """
        丢弃当前 driver executor，stuck 的线程任由其在后台慢慢死。

        这是网关稳定性的关键：当 pyserial read_until 在内核 IO 层 stuck 时，
        我们没法 cancel 那个线程，但可以"扔掉"它绑的 executor，让下次调用
        建一个干净的新 executor。
        """
        if self._driver_executor is not None:
            self._driver_executor.shutdown(wait=False)
            self._driver_executor = None

    def _ensure_action_executor(self) -> ThreadPoolExecutor:
        """惰性创建 action 专用单线程池。重连时同样会被丢弃重建。"""
        if self._action_executor is None:
            self._action_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=f"action-{self.device_id}",
            )
        return self._action_executor

    def _drop_action_executor(self) -> None:
        """
        丢弃 action executor，stuck 的 action 线程让它自己慢慢死。

        典型场景：驱动重连时 driver 整个对象被换掉，正在跑的 action 还握着
        旧 driver 引用——它操作的串口已经失效，要么 stuck 要么报异常。
        把绑它的 executor 一起丢弃，跟 driver_executor 一样的策略。
        """
        if self._action_executor is not None:
            self._action_executor.shutdown(wait=False)
            self._action_executor = None

    async def _read_property_async(self, prop: str) -> Any:
        """
        带超时的 property 读取。超时抛 asyncio.TimeoutError，由 _telemetry_loop 兜住。

        用 asyncio.wait + 专用 executor，而不是 wait_for + 全局 executor，
        避免 stuck 任务把全局线程池塞满，导致重连协程也无法调度。
        """
        ex = self._ensure_driver_executor()
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(ex, lambda: self._read_property_sync(prop))
        done, _pending = await asyncio.wait({future}, timeout=self.property_timeout)
        if future in done:
            return future.result()
        # 超时：future 还在 stuck，留在 executor 里慢慢死。挂一个 callback
        # 把它最终的异常 retrieve 掉，避免 asyncio 刷 "Future exception was
        # never retrieved" 的 ERROR 日志。
        _silence_future(future)
        raise asyncio.TimeoutError()

    async def _try_reconnect(self) -> None:
        """
        尝试重新创建驱动实例（重新打开串口）。
        典型场景：USB-RS485 适配器被热拔后再插回，旧 fd 失效，新 fd 出现。

        难点：pyserial 的 Serial.__init__() 在某些 USB 状态下会在内核层阻塞
        几分钟（termios/ioctl 调用 stuck），asyncio.wait_for + run_in_executor
        **不能真正超时**——线程一旦开始无法中断，wait_for 会等到 future 完成。
        所以这里用临时 ThreadPoolExecutor + shutdown(wait=False)，超时后让
        stuck 线程在后台自然结束，主流程立即继续。
        """
        if self._reconnecting:
            return
        self._reconnecting = True
        try:
            logger.warning(
                f"[DEV] {self.device_id} 串口连续失败 {self._io_error_count} 次，"
                f"尝试重新打开串口/重建驱动..."
            )

            # 关键：先丢弃 driver_executor + action_executor，连同里面 stuck 的
            # read/action 线程一起抛弃。重连时 driver 整个对象都被换掉，正在跑的
            # action 持有的旧 driver 引用上的串口已失效，让那个 stuck action 线程
            # 在被抛弃的 executor 里自生自灭即可。之后所有调用都在新 executor 上进行。
            self._drop_driver_executor()
            self._drop_action_executor()

            # 关闭旧 driver——也用临时 executor 隔离，避免 close() 自己卡死
            await self._close_old_driver_with_timeout(timeout=2.0)

            # 重建：用临时单线程池，超时后丢弃这个线程；健康检查也在内部完成
            new_driver = await self._build_driver_with_real_timeout(timeout=10.0)
            if new_driver is None:
                # 重连失败，检查是否超过放弃阈值（30 次 ≈ 30 秒）
                if self._io_error_count >= 30:
                    logger.error(
                        f"[DEV] {self.device_id} 串口连续失败 {self._io_error_count} 次，"
                        f"放弃重连，停止 worker（可能设备已拔出）"
                    )
                    await self.stop()
                    if self.on_device_lost:
                        self.on_device_lost(self.device_id)
                return

            self.driver = new_driver
            self._io_error_count = 0
            # 清空各 property 的连续超时计数
            self._consecutive_errors.clear()
            logger.info(f"[DEV] {self.device_id} 驱动重连成功 ✓")
        finally:
            self._reconnecting = False

    async def _close_old_driver_with_timeout(self, timeout: float) -> None:
        """关旧 driver/串口，用临时 executor + 超时保护，超时就直接放弃。"""
        ex = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"close-{self.device_id}"
        )
        loop = asyncio.get_event_loop()
        try:
            future = loop.run_in_executor(ex, self._close_driver_safely)
            done, _pending = await asyncio.wait({future}, timeout=timeout)
            if future not in done:
                logger.debug(
                    f"[DEV] {self.device_id} 关闭旧驱动超时（>{timeout}s），跳过"
                )
                _silence_future(future)
        finally:
            ex.shutdown(wait=False)

    async def _build_driver_with_real_timeout(self, timeout: float) -> Optional[Any]:
        """
        在专用临时线程池里跑 driver_factory，超时后立即放弃，并把 stuck 的
        线程"扔掉"（shutdown wait=False），不阻塞主循环。

        返回 None 表示重建失败/不健康，调用方应直接 return。
        返回非 None 表示重建出 driver（健康检查会在 _try_reconnect 里再做）。
        """
        ex = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"reconnect-{self.device_id}",
        )
        loop = asyncio.get_event_loop()
        try:
            future = loop.run_in_executor(ex, self.driver_factory)
            try:
                # asyncio.wait_for 超时会 cancel future，但对线程池 future
                # 来说 cancel 几乎肯定失败。我们用 wait + FIRST_COMPLETED
                # 来保证超时时立即返回。
                done, pending = await asyncio.wait({future}, timeout=timeout)
                if future in done:
                    new_driver = future.result()
                else:
                    # 线程还在 stuck（pyserial 的 Serial 内核调用阻塞）
                    logger.error(
                        f"[DEV] {self.device_id} 重建驱动超时（>{timeout}s, "
                        f"pyserial 在内核 IO 层 stuck），放弃这次尝试，5 秒后重试"
                    )
                    _silence_future(future)
                    await asyncio.sleep(5.0)
                    return None
            except Exception as e:
                logger.error(
                    f"[DEV] {self.device_id} 重建驱动失败: "
                    f"{type(e).__name__}: {e}（5 秒后再试）"
                )
                await asyncio.sleep(5.0)
                return None

            # 健康检查：driver 兜底退化为字符串视为失败
            if not self._driver_is_healthy(new_driver):
                logger.warning(
                    f"[DEV] {self.device_id} 驱动重建后串口仍未打开"
                    f"（设备未响应 / 串口忙），5 秒后重试"
                )
                try:
                    self._close_driver_obj_safely(new_driver)
                except Exception:
                    pass
                await asyncio.sleep(5.0)
                return None

            return new_driver
        finally:
            # 关键：不等线程！stuck 的线程让它自己慢慢死，不阻塞我们
            ex.shutdown(wait=False)

    @staticmethod
    def _driver_is_healthy(driver: Any) -> bool:
        """
        判断 driver 实例是否真的拿到了硬件接口。

        约定：如果 driver 有 ``hardware_interface`` 属性，且它是字符串，
        说明驱动 __init__ 失败了（被兜底成了 port 字符串），不健康。
        其他情况一律视为健康（包括 MockDevice / 没有这个属性的驱动）。
        """
        hw = getattr(driver, "hardware_interface", None)
        if hw is None:
            return True
        if isinstance(hw, str):
            return False
        return True

    @staticmethod
    def _close_driver_obj_safely(driver: Any) -> None:
        try:
            close_fn = getattr(driver, "close", None)
            if callable(close_fn):
                close_fn()
                return
            hw = getattr(driver, "hardware_interface", None)
            if hw is not None and hasattr(hw, "close"):
                hw.close()
        except Exception:
            pass

    def _close_driver_safely(self) -> None:
        """尽力关闭旧 driver 或它持有的串口对象。失败也无所谓。"""
        try:
            close_fn = getattr(self.driver, "close", None)
            if callable(close_fn):
                close_fn()
                return
            hw = getattr(self.driver, "hardware_interface", None)
            if hw is not None and hasattr(hw, "close"):
                hw.close()
        except Exception as e:
            logger.debug(f"[DEV] {self.device_id} 关闭旧驱动时异常（忽略）: {e}")

    def _read_property_sync(self, prop: str) -> Any:
        """
        读取属性的策略（兼容三种驱动写法）:

        1. 如果驱动有 ``get_<prop>()`` 方法 -> 调用它（这类驱动里 self.<prop> 通常只是缓存）
           例: RunzeSyringePump 里 self.status 是缓存值, get_status() 才会查询硬件
        2. 否则按 @property / 普通字段读取 self.<prop>
           例: MockDevice 里 self.temperature
        """
        getter = getattr(self.driver, f"get_{prop}", None)
        if callable(getter):
            return getter()
        return getattr(self.driver, prop)

    async def execute_action(self, action_name: str, action_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一个动作。返回 {"status": "success"/"failed", "return_info": {...}}。

        兼容前端两种命名空间：
        1. 驱动原始方法名:        initialize / set_position / pull_plunger
        2. registry 的 protocol 级 action 名（带 auto- 前缀）:
                                  auto-initialize / auto-set_position / auto-pull_plunger
                                  对应 yaml 的 action_value_mappings, 类型常为 UniLabJsonCommand

        参数解包：
        - 如果 action_args 形如 {"goal": {...}, "feedback": {}, "result": {}}（UniLabJsonCommand），
          自动取 goal 内容作为驱动方法的 **kwargs。
        - 否则原样把 action_args 作为 **kwargs 传入。
        """
        resolved_name, method = self._resolve_action_method(action_name)
        if method is None:
            return {
                "status": "failed",
                "return_info": {
                    "error": f"驱动 {self.device_id} 无方法 {action_name}（已尝试: {resolved_name}）"
                },
            }

        kwargs = self._unwrap_args(action_args)

        loop = asyncio.get_event_loop()
        try:
            if asyncio.iscoroutinefunction(method):
                # 协程动作：直接 await，没办法用 executor 隔离
                coro = method(**kwargs)
                result = await asyncio.wait_for(coro, timeout=self.action_timeout)
            else:
                # 同步动作走专用 action_executor（与 telemetry 的 driver_executor 分开），
                # 这样 start_stir(duration=10) 这类长阻塞动作不会卡住 property 轮询；
                # 串口的物理互斥由 driver 自己的 threading.Lock 兜底。
                # 用 asyncio.wait 而不是 wait_for，超时后立即返回不等线程
                ex = self._ensure_action_executor()
                future = loop.run_in_executor(ex, lambda: method(**kwargs))
                done, _pending = await asyncio.wait(
                    {future}, timeout=self.action_timeout
                )
                if future in done:
                    result = future.result()
                else:
                    _silence_future(future)
                    raise asyncio.TimeoutError()
            return {"status": "success", "return_info": {"result": _to_jsonable(result)}}
        except asyncio.TimeoutError:
            logger.error(
                f"[DEV] 执行 {self.device_id}.{resolved_name}({kwargs}) 超时（>{self.action_timeout}s）"
            )
            return {
                "status": "failed",
                "return_info": {"error": f"动作执行超时 (>{self.action_timeout}s)"},
            }
        except Exception as e:
            logger.error(
                f"[DEV] 执行 {self.device_id}.{resolved_name}({kwargs}) 异常: {e}"
            )
            logger.debug(traceback.format_exc())
            return {"status": "failed", "return_info": {"error": str(e)}}

    def _resolve_action_method(self, action_name: str):
        """根据 action_name 找驱动方法。返回 (尝试过的最终名, method 或 None)。"""
        candidates = [action_name]

        # 去掉 protocol 级前缀
        if action_name.startswith("auto-"):
            candidates.append(action_name[len("auto-"):])
        if action_name.startswith("auto_"):
            candidates.append(action_name[len("auto_"):])

        # 兼容 dash/underline 互换（前端有时把 set_position 显示为 set-position）
        for c in list(candidates):
            if "-" in c:
                candidates.append(c.replace("-", "_"))

        tried = []
        for name in candidates:
            if not name:
                continue
            tried.append(name)
            method = getattr(self.driver, name, None)
            if method is None or not callable(method) or isinstance(method, type):
                continue
            return name, method
        return " | ".join(tried), None

    @staticmethod
    def _unwrap_args(action_args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """解开 UniLabJsonCommand 的 {"goal":..., "feedback":..., "result":...} 包装。"""
        if not action_args:
            return {}
        if (
            isinstance(action_args, dict)
            and "goal" in action_args
            and isinstance(action_args["goal"], dict)
            and set(action_args.keys()) <= {"goal", "feedback", "result"}
        ):
            return action_args["goal"] or {}
        return action_args

    def list_actions(self) -> Dict[str, Dict[str, str]]:
        """
        反射列出驱动可调用的方法（用于 host_node_ready 上报）。

        约定：跳过 _ 开头、property、staticmethod 之外的所有 callable。
        """
        actions: Dict[str, Dict[str, str]] = {}
        cls = type(self.driver)
        for attr in dir(cls):
            if attr.startswith("_"):
                continue
            if attr.startswith("get_"):
                continue
            try:
                obj = getattr(cls, attr)
            except AttributeError:
                continue
            if isinstance(obj, property):
                continue
            if not callable(obj):
                continue
            actions[attr] = {
                "action_path": f"/devices/{self.device_id}/{attr}",
                "action_type": "ActionClient",
            }
        return actions


_SENTINEL = object()


def _silence_future(future: "asyncio.Future") -> None:
    """
    给一个我们已经放弃等待的 future 挂 done callback，把它最终的异常 "retrieve"
    一下。这样 asyncio 的 default_exception_handler 就不会刷 "Future exception
    was never retrieved" 的 ERROR 日志了。
    """
    def _swallow(f: "asyncio.Future") -> None:
        try:
            if not f.cancelled():
                f.exception()  # 触发"已 retrieve"标记
        except Exception:
            pass

    future.add_done_callback(_swallow)


def _is_io_error(e: BaseException) -> bool:
    """
    判断异常是否属于"串口/USB IO 失效"类，需要触发驱动重连。

    包含：
    - 所有 OSError 子类（IOError, FileNotFoundError, SerialException 等）
    - 驱动兜底退化为字符串后的 AttributeError（如 RunzeSyringePump 失败时
      把 self.hardware_interface 设成 str，调 .write()/.read() 会得到这种异常）
    - 驱动层自定义的连接/通信异常（按类名匹配，如 RunzeSyringePumpConnectionError、
      ModbusIOException 等，message 常常为空）
    """
    if isinstance(e, OSError):
        return True
    if isinstance(e, AttributeError):
        msg = str(e)
        # "'str' object has no attribute 'write'"  /  "'str' object has no attribute 'read'"
        if "'str' object" in msg and ("write" in msg or "read" in msg):
            return True
        if "hardware_interface" in msg:
            return True
    # 启发式：驱动层自定义的通信类异常一般类名里会带 ConnectionError / IOError /
    # CommunicationError / Timeout 等关键词。匹配上就视为 IO 错误。
    cls_name = type(e).__name__
    for kw in ("ConnectionError", "IOError", "CommunicationError", "TimeoutError", "PortNotOpen"):
        if kw in cls_name:
            return True
    return False


def _to_jsonable(value: Any) -> Any:
    """把驱动返回值尽量转成 JSON 可序列化形式。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    return str(value)


# --------------------------------------------------------------------------
# 假设备：用于不接真实硬件的链路验证
# --------------------------------------------------------------------------


class MockDevice:
    """
    Mock 设备，用于在没有真实硬件时验证网关 ↔ Schedule Server 链路。

    属性：
    - temperature: 20°C ± 0.5 的随机值
    - counter:     单调递增计数器

    动作：
    - reset(): 计数器归零
    - set_target(target: float): 记录目标值（无副作用）
    """

    device_type = "mock"

    def __init__(self, *, name: str = "mock") -> None:
        self.name = name
        self._counter = 0
        self._target: float = 0.0

    @property
    def temperature(self) -> float:
        return round(20.0 + random.uniform(-0.5, 0.5), 3)

    @property
    def counter(self) -> int:
        self._counter += 1
        return self._counter

    @property
    def target(self) -> float:
        return self._target

    def reset(self) -> bool:
        self._counter = 0
        return True

    def set_target(self, target: float) -> Dict[str, Any]:
        self._target = float(target)
        return {"target": self._target}
