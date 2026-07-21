"""
蓝牙(BLE)配网 GATT 外设服务

对应 ``BLE_PROTOCOL.md`` v1 的网关侧实现。网关作为 BLE Peripheral / GATT Server,
广播 ``UniLab-GW-XXXX``,APP(Central)连接后:

1. Read/Notify **DeviceInfo(A101)** 拿设备信息 + 状态 + 临时 X25519 公钥;
2. Write **ScanCtrl(A102)** ``{"cmd":"scan"}`` 触发 WiFi 扫描,网关逐条 Notify
   **ScanResult(A103)**;
3. Write **Provision(A104)** 提交 WiFi 凭证(明文 0x00 / 加密 0x01);
4. 网关在**纯 STA 在线模式**连 WiFi(不进 AP、不 reboot),通过 **Status(A105)**
   实时 Notify 进度/结果。

设计要点(为什么蓝牙能"在线不重启"):

- 蓝牙走独立 BT 射频,全程不碰 wlan0 的 STA 状态,因此复用
  ``WiFiManager._connect_wifi_in_sta_mode()``(``connect_wifi`` 在 ``_in_ap_mode=False``
  时走的路径)即可在线切换 WiFi + 验证公网,规避了 AP 方案里 unisoc 从 AP 切回 STA
  必须整机 reboot 的死穴。

依赖(仅 OPi/Linux 真机需要,开发机 import 本模块不会触发):

- ``bluez-peripheral``(基于 dbus-fast,Linux 原生 GATT server)—— 走 BlueZ。
- ``cryptography``(仅加密路径 0x01 需要;明文调试路径 0x00 不需要)。

两者都**惰性导入**(在 ``start()`` / 解密时才 import),所以在没有蓝牙的开发机上
``from unilabos.gateway.provisioning import BLEProvisioningServer`` 不会报错。

独立联调(不依赖 APP,用手机 nRF Connect 当"假 APP"):

    # 在 OPi 网关的 venv 里(需 root 或 bluetooth 组权限)
    python -m unilabos.gateway.provisioning.ble_server

    # 然后手机装 nRF Connect:
    #   1) 扫到 UniLab-GW-XXXX,连接
    #   2) 对 A103/A105 开 notify
    #   3) 往 A102 写 {"cmd":"scan"} (UTF-8),看 A103 逐条回 WiFi
    #   4) 往 A104 写「0x00 + {"ssid":"xx","password":"yy"} 的 UTF-8 字节」
    #      (即第一个字节 00,后面跟明文 JSON),看 A105 回进度直到 step=10
"""

import asyncio
import base64
import json
import logging
from typing import Callable, Optional

from unilabos.gateway.provisioning.wifi_manager import WiFiManager

logger = logging.getLogger("ble_server")

# ---- GATT UUID(与 BLE_PROTOCOL.md §2 一致)----
UUID_SERVICE = "0000a100-0000-1000-8000-00805f9b34fb"
UUID_DEVICE_INFO = "0000a101-0000-1000-8000-00805f9b34fb"  # Read + Notify
UUID_SCAN_CTRL = "0000a102-0000-1000-8000-00805f9b34fb"    # Write
UUID_SCAN_RESULT = "0000a103-0000-1000-8000-00805f9b34fb"  # Notify
UUID_PROVISION = "0000a104-0000-1000-8000-00805f9b34fb"    # Write
UUID_STATUS = "0000a105-0000-1000-8000-00805f9b34fb"       # Notify

# ---- Provision 载荷版本字节(BLE_PROTOCOL.md §6)----
_PROV_VER_PLAINTEXT = 0x00  # 调试:后续直接是明文 JSON
_PROV_VER_ENCRYPTED = 0x01  # 正式:X25519+AES-GCM

# HKDF info,双端必须一致
_HKDF_INFO = b"unilab-ble-prov-v1"


def _read_wlan_mac() -> str:
    """读 wlan0 MAC(去冒号小写),失败返回空串。用作 sn。"""
    try:
        with open("/sys/class/net/wlan0/address", "r", encoding="ascii") as f:
            return f.read().strip().replace(":", "").lower()
    except Exception:
        return ""


class BLEProvisioningServer:
    """BLE 配网服务器(GATT Peripheral)。

    :param wifi_mgr: 复用的 WiFiManager(在线扫描/连接)。
    :param on_success: 配网成功回调 ``on_success(ssid)``,由 main.py 传入以退出配网态。
    :param machine_name: 网关机器名(仅日志展示)。
    :param fw_version: 固件版本,进 DeviceInfo。
    :param allow_plaintext: 是否接受明文 Provision(0x00)。bring-up 期 True,生产应 False。
    """

    def __init__(
        self,
        wifi_mgr: WiFiManager,
        on_success: Optional[Callable[[Optional[str]], None]] = None,
        machine_name: str = "",
        fw_version: str = "1.0.0",
        allow_plaintext: bool = True,
    ) -> None:
        self._wifi = wifi_mgr
        self._on_success = on_success
        self._machine_name = machine_name
        self._fw = fw_version
        self._allow_plaintext = allow_plaintext

        # 由 ap_ssid(UniLab-Gateway-XXXX)推出协议约定的名字 UniLab-GW-XXXX
        suffix = wifi_mgr.ap_ssid.rsplit("-", 1)[-1] if wifi_mgr.ap_ssid else "0000"
        self._local_name = f"UniLab-GW-{suffix}"
        self._sn = _read_wlan_mac() or suffix.lower()

        self._state = "need_provision"  # need_provision / connecting / online
        self._provisioning = False       # 一次只处理一个 Provision

        # 运行时
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bus = None
        self._service = None       # _ProvisioningService 实例
        self._adv = None
        self._adapter = None

        # X25519 临时密钥(每"会话"轮换;见 _rotate_keys)
        self._x25519_priv = None
        self._pubkey_b64 = ""

    # =====================================================================
    # 生命周期
    # =====================================================================
    async def start(self) -> None:
        """注册 GATT 服务并开始广播。需要 BlueZ 在跑、且有蓝牙权限。"""
        # 惰性导入,开发机没装也不影响 import 本模块
        from bluez_peripheral.util import Adapter, get_message_bus
        from bluez_peripheral.advert import Advertisement
        from bluez_peripheral.agent import NoIoAgent

        self._loop = asyncio.get_running_loop()
        self._rotate_keys()

        self._bus = await get_message_bus()

        # Just Works 配对代理(我们用应用层加密,不依赖链路层配对,但注册 agent
        # 可避免部分手机弹配对框卡住)
        agent = NoIoAgent()
        await agent.register(self._bus)

        self._service = _ProvisioningService(self)
        await self._service.register(self._bus)

        self._adapter = await Adapter.get_first(self._bus)
        try:
            await self._adapter.set_powered(True)
            await self._adapter.set_alias(self._local_name)
        except Exception as e:
            logger.debug(f"[BLE] 设置 adapter powered/alias 失败(继续): {e}")

        # 广播:带 Service UUID 供 APP 过滤;timeout=0 表示不自动停
        self._adv = Advertisement(self._local_name, [UUID_SERVICE], 0x0000, 0)
        await self._adv.register(self._bus, self._adapter)

        logger.info("=" * 60)
        logger.info("[BLE] 蓝牙配网服务已启动")
        logger.info(f"[BLE]   广播名: {self._local_name}")
        logger.info(f"[BLE]   sn:     {self._sn}")
        logger.info(f"[BLE]   明文调试: {'开' if self._allow_plaintext else '关'}")
        logger.info("[BLE]   用 APP / nRF Connect 扫 UniLab-GW-* 连接配网")
        logger.info("=" * 60)

    async def stop(self) -> None:
        """停止广播并释放资源。"""
        try:
            if self._adv is not None:
                await self._adv.unregister()
        except Exception as e:
            logger.debug(f"[BLE] 注销广播失败: {e}")
        try:
            if self._service is not None:
                await self._service.unregister()
        except Exception as e:
            logger.debug(f"[BLE] 注销服务失败: {e}")
        try:
            if self._bus is not None:
                self._bus.disconnect()
        except Exception as e:
            logger.debug(f"[BLE] 断开 dbus 失败: {e}")
        self._adv = self._service = self._bus = None
        logger.info("[BLE] 蓝牙配网服务已停止")

    # =====================================================================
    # 密钥
    # =====================================================================
    def _rotate_keys(self) -> None:
        """轮换一对临时 X25519 密钥(每次配网会话/失败重试后调用)。

        没装 cryptography 时不影响明文调试路径,只是 pubkey 为空、加密路径不可用。
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                PublicFormat,
            )

            self._x25519_priv = X25519PrivateKey.generate()
            # 用显式 Raw 编码(public_bytes_raw() 仅 cryptography>=40 才有)
            pub = self._x25519_priv.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
            self._pubkey_b64 = base64.b64encode(pub).decode("ascii")
        except Exception as e:
            self._x25519_priv = None
            self._pubkey_b64 = ""
            logger.warning(f"[BLE] 生成 X25519 密钥失败(加密路径将不可用): {e}")

    # =====================================================================
    # 特征读/写回调(由 _ProvisioningService 转发,运行在 asyncio 事件循环线程)
    # =====================================================================
    def device_info_bytes(self) -> bytes:
        """DeviceInfo(A101)读取内容。"""
        info = {
            "name": self._local_name,
            "sn": self._sn,
            "fw": self._fw,
            "state": self._state,
            "pubkey": self._pubkey_b64,
        }
        return json.dumps(info, ensure_ascii=False).encode("utf-8")

    def on_scan_ctrl(self, raw: bytes) -> None:
        """ScanCtrl(A102)写入:``{"cmd":"scan"}``。"""
        try:
            cmd = json.loads(raw.decode("utf-8")).get("cmd")
        except Exception:
            logger.warning(f"[BLE] ScanCtrl 无法解析: {raw!r}")
            return
        if cmd == "scan":
            self._spawn(self._do_scan())
        else:
            logger.warning(f"[BLE] ScanCtrl 未知命令: {cmd}")

    def on_provision(self, raw: bytes) -> None:
        """Provision(A104)写入:提交 WiFi 凭证。"""
        if self._provisioning:
            self._emit_status(29, False, "正在处理上一配网请求,请稍候")
            return
        self._spawn(self._do_provision(raw))

    # =====================================================================
    # 业务流程(异步)
    # =====================================================================
    async def _do_scan(self) -> None:
        """在纯 STA 模式扫描 WiFi,逐条 Notify ScanResult。"""
        logger.info("[BLE] 收到扫描请求,STA 模式扫描 WiFi…")
        try:
            wifi_list = await self._loop.run_in_executor(None, self._wifi.scan_wifi)
        except Exception as e:
            logger.error(f"[BLE] 扫描失败: {e}")
            self._notify_scan_result({"done": True, "count": 0, "error": str(e)})
            return
        for w in wifi_list:
            self._notify_scan_result({
                "ssid": w.get("ssid", ""),
                "signal": w.get("signal", 0),
                "security": w.get("security", "Open"),
            })
        self._notify_scan_result({"done": True, "count": len(wifi_list)})
        logger.info(f"[BLE] 扫描完成,已下发 {len(wifi_list)} 个 WiFi")

    async def _do_provision(self, raw: bytes) -> None:
        """解析凭证 → STA 在线连接 → Status 实时回报(全程不 reboot)。"""
        self._provisioning = True
        try:
            try:
                ssid, password = self._parse_provision(raw)
            except Exception as e:
                logger.warning(f"[BLE] Provision 解析失败: {e}")
                self._emit_status(29, False, f"凭证解析失败: {e}")
                return

            self._emit_status(0, None, "已收到凭证")
            self._emit_status(1, None, "正在连接 WiFi…")
            self._set_state("connecting")

            # 关键:_in_ap_mode 必须为 False,connect_wifi 才走在线 STA 路径
            self._wifi._in_ap_mode = False
            success, err = await self._loop.run_in_executor(
                None, self._wifi.connect_wifi, ssid, password
            )

            if success:
                logger.info(f"[BLE] ✓ 配网成功: {ssid}")
                self._emit_status(10, True, "配网成功,已联网")
                self._set_state("online")
                if self._on_success is not None:
                    try:
                        self._on_success(ssid)
                    except Exception as e:
                        logger.error(f"[BLE] on_success 回调异常: {e}")
            else:
                step = self._map_error_step(err)
                logger.warning(f"[BLE] ✗ 配网失败 step={step} err={err}")
                self._emit_status(step, False, err or "配网失败")
                self._set_state("need_provision")
                # 失败后为下一次重试换一把新密钥(蓝牙不断、不重启)
                self._rotate_keys()
        finally:
            self._provisioning = False

    # =====================================================================
    # 凭证解析(明文 0x00 / 加密 0x01)
    # =====================================================================
    def _parse_provision(self, raw: bytes) -> tuple[str, str]:
        if not raw:
            raise ValueError("空数据")
        ver = raw[0]
        if ver == _PROV_VER_PLAINTEXT:
            if not self._allow_plaintext:
                raise ValueError("明文配网已禁用(仅支持加密 0x01)")
            obj = json.loads(raw[1:].decode("utf-8"))
        elif ver == _PROV_VER_ENCRYPTED:
            obj = json.loads(self._decrypt_provision(raw).decode("utf-8"))
        else:
            raise ValueError(f"未知 Provision 版本字节 0x{ver:02x}")

        ssid = obj.get("ssid", "")
        if not ssid:
            raise ValueError("缺少 ssid")
        return ssid, obj.get("password", "")

    def _decrypt_provision(self, raw: bytes) -> bytes:
        """解密 0x01 载荷:[ver|app_pubkey(32)|nonce(12)|ciphertext+tag]。"""
        if self._x25519_priv is None:
            raise ValueError("网关未就绪加密密钥,无法解密")
        if len(raw) < 1 + 32 + 12 + 16:
            raise ValueError("加密载荷长度不足")
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes

        app_pub = raw[1:33]
        nonce = raw[33:45]
        ct = raw[45:]
        shared = self._x25519_priv.exchange(X25519PublicKey.from_public_bytes(app_pub))
        key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO
        ).derive(shared)
        return AESGCM(key).decrypt(nonce, ct, None)

    # =====================================================================
    # Notify 辅助
    # =====================================================================
    @staticmethod
    def _map_error_step(err: str) -> int:
        """把 WiFiManager 的中文错误映射到 Status.step(BLE_PROTOCOL.md §5)。"""
        e = err or ""
        if "密码" in e:
            return 20
        if "找不到" in e:
            return 21
        if "公网" in e:
            return 22
        if "超时" in e:
            return 23
        return 29

    def _emit_status(self, step: int, ok: Optional[bool], msg: str) -> None:
        payload = {"step": step, "ok": ok, "msg": msg}
        logger.info(f"[BLE] Status → {payload}")
        if self._service is not None:
            self._service.notify_status(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            )

    def _notify_scan_result(self, obj: dict) -> None:
        if self._service is not None:
            self._service.notify_scan_result(
                json.dumps(obj, ensure_ascii=False).encode("utf-8")
            )

    def _set_state(self, state: str) -> None:
        self._state = state
        if self._service is not None:
            self._service.notify_device_info(self.device_info_bytes())

    def _spawn(self, coro) -> None:
        """在事件循环里安全地起一个后台任务(回调可能来自 dbus 线程上下文)。"""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(coro))


def _build_service_class():
    """惰性构建 GATT Service 子类(依赖 bluez_peripheral,故延迟到运行时)。"""
    from bluez_peripheral.gatt.service import Service
    from bluez_peripheral.gatt.characteristic import (
        characteristic,
        CharacteristicFlags as CharFlags,
    )

    class _ProvisioningService(Service):
        """UniLab Provisioning GATT Service(5 个特征)。"""

        def __init__(self, server: "BLEProvisioningServer"):
            self._server = server
            super().__init__(UUID_SERVICE, True)

        # --- A101 DeviceInfo: Read + Notify ---
        @characteristic(UUID_DEVICE_INFO, CharFlags.READ | CharFlags.NOTIFY)
        def device_info(self, options):
            return self._server.device_info_bytes()

        # --- A102 ScanCtrl: Write ---
        @characteristic(UUID_SCAN_CTRL, CharFlags.WRITE)
        def scan_ctrl(self, options):
            return b""

        @scan_ctrl.setter
        def scan_ctrl(self, value, options):
            self._server.on_scan_ctrl(bytes(value))

        # --- A103 ScanResult: Notify ---
        @characteristic(UUID_SCAN_RESULT, CharFlags.NOTIFY)
        def scan_result(self, options):
            return b"{}"

        # --- A104 Provision: Write ---
        @characteristic(UUID_PROVISION, CharFlags.WRITE)
        def provision(self, options):
            return b""

        @provision.setter
        def provision(self, value, options):
            self._server.on_provision(bytes(value))

        # --- A105 Status: Notify ---
        @characteristic(UUID_STATUS, CharFlags.NOTIFY)
        def status(self, options):
            return b"{}"

        # 供 server 主动推送 notify 的入口
        def notify_device_info(self, data: bytes) -> None:
            self.device_info.changed(data)

        def notify_scan_result(self, data: bytes) -> None:
            self.scan_result.changed(data)

        def notify_status(self, data: bytes) -> None:
            self.status.changed(data)

    return _ProvisioningService


# 模块级占位:真正的类在 start() 里通过 _build_service_class() 生成。
# 这样开发机 import 本模块时不会因缺 bluez_peripheral 报错。
def _ProvisioningService(server):  # noqa: N802 - 保持与内部类同名的工厂
    cls = _build_service_class()
    return cls(server)


async def _amain() -> int:
    """独立联调入口:起一个明文模式 BLE 配网服务,配合手机 nRF Connect 测试。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    wifi = WiFiManager()
    wifi._in_ap_mode = False  # 全程纯 STA,不进 AP

    def _on_success(ssid):
        logger.info(f"[BLE][test] 配网成功回调 ssid={ssid}(独立联调模式不退出)")

    server = BLEProvisioningServer(
        wifi, on_success=_on_success, machine_name="ble-test", allow_plaintext=True
    )
    await server.start()
    logger.info("[BLE][test] 运行中,Ctrl+C 退出…")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain()))
