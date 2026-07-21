"""
液面检测核心模块，被 debug.py 和 detect.py 共同引用。
"""
import cv2
import numpy as np


def detect_liquid_level(crop, blur, canny_low, canny_high,
                         top_margin, bot_margin,
                         h_low, h_high, s_low, s_high, v_low, v_high,
                         use_color):
    """
    检测 ROI 内的液面位置。

    返回:
        level_y  : 液面 y 坐标（crop 内像素），None 表示未检测到
        vis      : 带标注的 ROI 彩色图
        edge_vis : 边缘图 + 强度曲线（调试用）
        mask_vis : 颜色掩码叠加图（调试用）
    """
    h, w = crop.shape[:2]
    vis  = crop.copy()

    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,
                       np.array([h_low,  s_low,  v_low]),
                       np.array([h_high, s_high, v_high]))

    mask_overlay = crop.copy()
    mask_overlay[mask == 0] = (mask_overlay[mask == 0] * 0.25).astype(np.uint8)
    label = f"Color filter: {'ON' if use_color else 'OFF (preview)'}"
    cv2.putText(mask_overlay, label, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 255, 0) if use_color else (0, 165, 255), 1)
    mask_vis = mask_overlay

    gray = cv2.cvtColor(
        cv2.bitwise_and(crop, crop, mask=mask) if use_color else crop,
        cv2.COLOR_BGR2GRAY
    )
    blurred = cv2.GaussianBlur(gray, (blur, blur), 0)
    edges   = cv2.Canny(blurred, canny_low, canny_high)

    top_px = int(h * top_margin / 100)
    bot_px = int(h * bot_margin / 100)
    if top_px > 0:
        edges[:top_px, :] = 0
    if bot_px > 0:
        edges[h - bot_px:, :] = 0

    bar_w    = 60
    edge_vis = np.zeros((h, w + bar_w, 3), dtype=np.uint8)
    edge_vis[:, :w] = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    row_strength = edges.sum(axis=1)
    if row_strength.max() == 0:
        for img in (vis, edge_vis, mask_vis):
            cv2.putText(img, "No edge detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return None, vis, edge_vis, mask_vis

    level_y = int(np.argmax(row_strength))
    max_s   = float(row_strength.max())

    for row_i, s in enumerate(row_strength):
        bar_len = int(s / max_s * (bar_w - 4))
        if bar_len > 0:
            cv2.line(edge_vis, (w + 2, row_i), (w + 2 + bar_len, row_i), (180, 180, 0), 1)
    cv2.line(edge_vis, (w, level_y), (w + bar_w, level_y), (0, 255, 0), 2)

    label_y = max(level_y - 8, 14)
    for img in (vis, edge_vis, mask_vis):
        cv2.line(img, (0, level_y), (img.shape[1], level_y), (0, 255, 0), 2)
        cv2.putText(img, f"y = {level_y} px", (10, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return level_y, vis, edge_vis, mask_vis


def open_cap(camera_index, roi):
    """打开摄像头并校验 ROI，返回 (cap, roi)。"""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera index={camera_index}")
        return None, None

    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[OK] Camera opened: index={camera_index}, resolution={cam_w}x{cam_h}")

    if roi is not None:
        x, y, w, h = roi
        x = max(0, min(x, cam_w - 1))
        y = max(0, min(y, cam_h - 1))
        w = max(1, min(w, cam_w - x))
        h = max(1, min(h, cam_h - y))
        roi = (x, y, w, h)
        print(f"[OK] ROI: x={x}, y={y}, w={w}, h={h}")
    else:
        roi = (0, 0, cam_w, cam_h)

    for _ in range(5):
        cap.read()

    return cap, roi
