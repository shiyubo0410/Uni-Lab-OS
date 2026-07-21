"""
液面检测 —— 正式检测模式
把 debug.py 调试好的参数填入下方常量，运行后只显示 ROI 窗口。
"""
import cv2
from test import detect_liquid_level, open_cap

# ── 摄像头和 ROI ─────────────────────────────────────────────
CAMERA_INDEX = 1
ROI = (250, 50, 200, 320)   # (x, y, w, h)，单位像素；None = 全图

# ── 从 debug.py 复制过来的参数 ───────────────────────────────
BLUR        = 3
CANNY_LOW   = 30
CANNY_HIGH  = 66
TOP_MARGIN  = 10
BOT_MARGIN  = 10
USE_COLOR   = 1
H_LOW, H_HIGH = 23, 38
S_LOW, S_HIGH = 12, 150
V_LOW, V_HIGH = 135, 230
# ────────────────────────────────────────────────────────────


def main():
    cap, roi = open_cap(CAMERA_INDEX, ROI)
    if cap is None:
        return

    cv2.namedWindow("ROI", cv2.WINDOW_NORMAL)
    print("按 'q' 退出")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rx, ry, rw, rh = roi
        level_y, vis, _, _ = detect_liquid_level(
            frame[ry:ry+rh, rx:rx+rw],
            BLUR, CANNY_LOW, CANNY_HIGH, TOP_MARGIN, BOT_MARGIN,
            H_LOW, H_HIGH, S_LOW, S_HIGH, V_LOW, V_HIGH, USE_COLOR
        )

        if level_y is not None:
            print(f"\r[Level] y={level_y} px", end="", flush=True)

        cv2.imshow("ROI", vis)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    print()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
