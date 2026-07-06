"""
首次启动时把网关 + 设备注册到 Lab 资源树。

通过 POST /edge/material 实现，与 unilabos/app/web/client.py:resource_tree_add 等价。
设备节点的 schema 参考 req_resource_tree_add.json 样例。

UUID 通过 (machine_name, device_id) 计算 uuid5，幂等——多次启动不会重复创建节点。

策略（实战调出来的）：
1. 先单独 POST host_node（class=host_node，parent_uuid=""，mount_uuid=lab_uuid_or_空）。
   后端只接受预注册过的 class 类型，host_node 是肯定能过的。
2. 拿到 host_node 的 cloud_uuid 后，逐个 POST 设备节点：
   - parent_uuid 设为 host_node 的 cloud_uuid（让设备挂在网关下）
   - class 用 yaml 里的 registry_class，没填则降级为 "host_node"（保险但分类不准）
3. 任何一步失败都 warning 但不阻断 WebSocket 启动。
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_module
from typing import Any, Dict, List, Optional, Tuple

import requests

from unilabos.config.config import BasicConfig

logger = logging.getLogger(__name__)


_GATEWAY_NS = uuid_module.UUID("00000000-0000-4000-a000-000000000001")


def deterministic_uuid(*parts: str) -> str:
    """基于 parts 生成稳定的 UUID5（每次启动一致）。"""
    return str(uuid_module.uuid5(_GATEWAY_NS, "/".join(parts)))


def _default_pose() -> Dict[str, Any]:
    return {
        "size": {"depth": 0.0, "width": 0.0, "height": 0.0},
        "scale": {"x": 0.0, "y": 0.0, "z": 0.0},
        "layout": "x-y",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "position3d": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "cross_section_type": "rectangle",
    }


def _build_host_node(machine_name: str) -> Dict[str, Any]:
    return {
        "id": "host_node",
        "uuid": deterministic_uuid(machine_name, "host_node"),
        "name": machine_name,
        "description": "Uni-Lab IoT 网关",
        "schema": {},
        "model": {},
        "icon": "",
        "parent_uuid": "",
        "type": "device",
        "class": "host_node",
        "pose": _default_pose(),
        "config": {},
        "data": {},
        "extra": {},
    }


def _build_device_node(
    machine_name: str,
    cfg: Dict[str, Any],
    parent_cloud_uuid: str,
) -> Dict[str, Any]:
    """
    根据 yaml 配置构建一个设备节点。
    parent_cloud_uuid 应该是 host_node POST 后云端返回的 cloud_uuid。
    """
    device_id = cfg["device_id"]
    # registry_class 优先用 yaml 显式声明的值（如 syringe_pump_with_valve.runze.SY03B-T06）
    # 没填则降级为 host_node 保证能注册成功
    registry_class = cfg.get("registry_class") or "host_node"

    return {
        "id": device_id,
        "uuid": deterministic_uuid(machine_name, "device", device_id),
        "name": cfg.get("name", device_id),
        "description": cfg.get("description", ""),
        "schema": {},
        "model": {},
        "icon": "",
        "parent_uuid": parent_cloud_uuid,
        "type": "device",
        "class": registry_class,
        "pose": _default_pose(),
        "config": cfg.get("init", {}) or {},
        "data": {},
        "extra": {},
    }


def _post_nodes(
    url: str,
    headers: Dict[str, str],
    nodes: List[Dict[str, Any]],
    mount_uuid: str,
    timeout: int,
) -> Tuple[bool, Optional[List[Dict[str, Any]]]]:
    """
    POST /edge/material 一组节点。
    返回 (是否成功, 云端返回的节点列表)。云端列表里每项含 cloud_uuid。
    """
    payload = {"nodes": nodes, "mount_uuid": mount_uuid}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        logger.error(f"[REG] POST {url} 异常: {e}")
        return False, None

    if r.status_code != 200:
        logger.error(f"[REG] POST 失败 status={r.status_code}: {r.text[:300]}")
        return False, None

    try:
        res = r.json()
    except Exception:
        logger.error(f"[REG] 响应非 JSON: {r.text[:300]}")
        return False, None

    if res.get("code") == 0:
        return True, res.get("data") or []

    msg = res.get("message") or res.get("msg") or r.text[:200]
    logger.warning(f"[REG] POST code={res.get('code')} msg={msg}")
    return False, None


def register_sync(
    base_url: str,
    machine_name: str,
    devices_cfg: List[Dict[str, Any]],
    mount_uuid: str = "",
    timeout: int = 30,
) -> bool:
    """
    同步把网关 + 设备注册到 lab 资源树。

    Returns:
        True: host_node 注册成功（即使设备失败也算部分成功，前端至少能看到网关）
        False: host_node 注册都没过
    """
    headers = {
        "Authorization": f"Lab {BasicConfig.auth_secret()}",
        "Content-Type": "application/json",
    }
    url = f"{base_url.rstrip('/')}/edge/material"

    # ---------- 第 1 步: 注册 host_node ----------
    host = _build_host_node(machine_name)
    logger.info(
        f"[REG] 注册 host_node 到 {url} mount_uuid={mount_uuid or 'ROOT'} "
        f"name={machine_name} uuid={host['uuid'][:8]}..."
    )

    ok, host_resp = _post_nodes(url, headers, [host], mount_uuid, timeout)
    if not ok or not host_resp:
        logger.error("[REG] host_node 注册失败，前端将看不到网关")
        return False

    host_cloud_uuid = host_resp[0].get("cloud_uuid") or host_resp[0].get("uuid")
    logger.info(
        f"[REG] host_node 注册成功: cloud_uuid={host_cloud_uuid[:8] if host_cloud_uuid else '?'}..."
    )

    # ---------- 第 2 步: 逐个注册设备 ----------
    if not devices_cfg:
        logger.info("[REG] 没有设备需要注册")
        return True

    success_count = 0
    for cfg in devices_cfg:
        node = _build_device_node(machine_name, cfg, parent_cloud_uuid=host_cloud_uuid)
        logger.info(
            f"[REG]   注册设备 {node['id']} class={node['class']} "
            f"parent={host_cloud_uuid[:8] if host_cloud_uuid else '?'}..."
        )
        # 每个设备单独 POST，单个失败不影响其它（mount_uuid 仍传给云端做权限/lab 校验）
        ok, _ = _post_nodes(url, headers, [node], mount_uuid, timeout)
        if ok:
            success_count += 1
        else:
            logger.warning(
                f"[REG]   设备 {node['id']} 注册失败（class={node['class']} 可能后端未注册此类型，"
                f"或要去 unilabos/registry/devices/*.yaml 里加 registry 定义）"
            )

    logger.info(
        f"[REG] 完成: host_node + 设备 {success_count}/{len(devices_cfg)} 注册成功"
    )
    return True


async def register_async(
    base_url: str,
    machine_name: str,
    devices_cfg: List[Dict[str, Any]],
    mount_uuid: str = "",
) -> bool:
    """注册的 asyncio 包装，避免阻塞事件循环。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, register_sync, base_url, machine_name, devices_cfg, mount_uuid, 30
    )
