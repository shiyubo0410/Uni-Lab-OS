"""网关侧: 无 ROS 构建并上传"注册表模板"(设备/资源类型定义)到云端。

背景:
    节点注册(POST /edge/material)要求设备/资源的**类型模板**已存在于用户实验室,
    否则后端返回 'material resource template not exist' (code 22020)。
    本模块在节点注册前, 先用 registry 的**纯 Python 构建路径**(无 ROS2/rclpy/DDS)
    在网关本地构建注册表, 并通过 HTTP(POST /lab/resource) 上报为模板。

    这样用户从网站下载的 @device/@action 新驱动也会被自动构建出 schema 并上报,
    实现"插上线即可用"。

实现说明:
    刻意**不** import unilabos.app.register / unilabos.app.web.client ——
    它们的父包 __init__ 会拉起 server/api/host_node 等 ROS 依赖(rosidl_parser/rclpy)。
    这里参照 gateway/register.py 自包含地拼 payload + 直接 HTTP, 全程纯 Python。
"""

from __future__ import annotations

import asyncio
import gzip
import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


def _post_resources(
    url: str, headers: Dict[str, str], resources: List[Dict[str, Any]], tag: str, timeout: int
) -> bool:
    """gzip POST 一批模板到 /lab/resource, 返回是否成功。"""
    from unilabos.utils.tools import fast_dumps

    if not resources:
        return True
    try:
        body = gzip.compress(fast_dumps({"resources": resources}))
        r = requests.post(url, data=body, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[REG-TPL] POST {tag} 异常: {e}")
        return False

    if r.status_code not in (200, 201):
        logger.error(f"[REG-TPL] {tag} 上传失败 status={r.status_code}: {r.text[:300]}")
        return False
    try:
        res = r.json()
    except Exception:  # noqa: BLE001
        logger.warning(f"[REG-TPL] {tag} 响应非 JSON: {r.text[:200]}")
        return True
    if isinstance(res, dict) and res.get("code") not in (0, None):
        logger.error(f"[REG-TPL] {tag} 上传返回 code={res.get('code')} msg={res.get('message') or res.get('msg')}")
        return False
    skipped = (res.get("data") or {}).get("skipped") if isinstance(res, dict) else False
    logger.info(f"[REG-TPL] {tag} 上传成功 {len(resources)} 个" + ("（内容未变化，跳过）" if skipped else ""))
    return True


def upload_registry_templates_sync(base_url: str = "", timeout: int = 60) -> bool:
    """同步构建注册表并上传模板。返回是否上传成功(失败不抛, 仅告警)。"""
    try:
        from unilabos.config.config import BasicConfig, HTTPConfig
        from unilabos.registry.registry import build_registry, HAS_ROS
        from unilabos.utils.tools import normalize_json
    except Exception as e:  # noqa: BLE001
        logger.error(f"[REG-TPL] 依赖导入失败, 跳过注册表模板上传: {e}")
        return False

    remote = (base_url or HTTPConfig.remote_addr).rstrip("/")
    auth = BasicConfig.auth_secret()
    if not auth:
        logger.warning("[REG-TPL] 未配置 ak/sk(auth_secret 为空), 跳过注册表模板上传")
        return False

    # 启用注册表缓存：registry 仅在 BasicConfig.working_dir 非空时读写 registry_cache.pkl。
    # 网关进程从不设 working_dir → 缓存被禁用 → 每次启动全量重建注册表(AST+YAML, ~30s)。
    # 这里指向 /data 下的持久可写目录(root 启动, 重启/换库后仍在), 让第二次起秒级命中缓存。
    if not BasicConfig.working_dir:
        import os

        for cand in ("/data/unilab-gateway", os.path.expanduser("~/.cache/unilab-gateway")):
            try:
                os.makedirs(cand, exist_ok=True)
                BasicConfig.working_dir = cand
                break
            except Exception:  # noqa: BLE001
                continue
        logger.info(f"[REG-TPL] 注册表缓存目录: {BasicConfig.working_dir or '(不可用, 将每次重建)'}")

    logger.info(f"[REG-TPL] 开始构建注册表(HAS_ROS={HAS_ROS})并上传模板到 {remote} ...")
    try:
        reg = build_registry()
    except Exception as e:  # noqa: BLE001
        logger.error(f"[REG-TPL] 注册表构建失败, 跳过模板上传: {e}")
        return False

    headers = {
        "Authorization": f"Lab {auth}",
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
    }
    url = f"{remote}/lab/resource"

    try:
        devices = [normalize_json(d) for d in reg.obtain_registry_device_info()]
        resources = list(reg.obtain_registry_resource_info())
    except Exception as e:  # noqa: BLE001
        logger.error(f"[REG-TPL] 收集注册表数据失败: {e}")
        return False

    logger.info(f"[REG-TPL] 待上传: {len(devices)} 设备类型, {len(resources)} 资源类型")
    ok_dev = _post_resources(url, headers, devices, "设备模板", timeout)
    ok_res = _post_resources(url, headers, resources, "资源模板", timeout)
    ok = ok_dev and ok_res
    logger.info(f"[REG-TPL] 注册表模板上传{'完成' if ok else '部分失败'}")
    return ok


async def upload_registry_templates(base_url: str = "") -> bool:
    """异步包装, 避免阻塞事件循环(注册表构建可能耗时数十秒)。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, upload_registry_templates_sync, base_url)
