"""
液面检测 —— 调试模式
拖动滑条实时调整参数，按 q 退出后终端打印最终参数，复制到 detect.py 中使用。
"""
import cv2
from test import detect_liquid_level, open_cap

# ── 在这里修改摄像头编号和 ROI ──────────────────────────────────
CAMERA_INDEX = 1
ROI = (250, 50, 200, 320)   # (x, y, w, h)，单位像素；None = 全图
# ────────────────────────────────────────────────────────────────


def _nothing(_):
    pass


def main():
    cap, roi = open_cap(CAMERA_INDEX, ROI)
    if cap is None:
        return

    cv2.namedWindow("Camera",     cv2.WINDOW_NORMAL)
    cv2.namedWindow("ROI",        cv2.WINDOW_NORMAL)
    cv2.namedWindow("Edge Map",   cv2.WINDOW_NORMAL)
    cv2.namedWindow("Color Mask", cv2.WINDOW_NORMAL)

    W = "Edge Map"
    cv2.createTrackbar("Blur",         W, 1,   50,  _nothing)
    cv2.createTrackbar("Canny Low",    W, 30,  255, _nothing)
    cv2.createTrackbar("Canny High",   W, 90,  255, _nothing)
    cv2.createTrackbar("Top margin%",  W, 10,  50,  _nothing)
    cv2.createTrackbar("Bot margin%",  W, 10,  50,  _nothing)
    cv2.createTrackbar("Color filter", W, 0,   1,   _nothing)
    cv2.createTrackbar("H Low",        W, 0,   179, _nothing)
    cv2.createTrackbar("H High",       W, 179, 179, _nothing)
    cv2.createTrackbar("S Low",        W, 0,   255, _nothing)
    cv2.createTrackbar("S High",       W, 255, 255, _nothing)
    cv2.createTrackbar("V Low",        W, 0,   255, _nothing)
    cv2.createTrackbar("V High",       W, 255, 255, _nothing)

    print("拖动 Edge Map 窗口中的滑条调参  |  按 'q' 退出并打印参数")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        blur       = cv2.getTrackbarPos("Blur",         W) * 2 + 1
        canny_low  = cv2.getTrackbarPos("Canny Low",    W)
        canny_high = cv2.getTrackbarPos("Canny High",   W)
        top_m      = cv2.getTrackbarPos("Top margin%",  W)
        bot_m      = cv2.getTrackbarPos("Bot margin%",  W)
        use_color  = cv2.getTrackbarPos("Color filter", W)
        h_low      = cv2.getTrackbarPos("H Low",  W)
        h_high     = cv2.getTrackbarPos("H High", W)
        s_low      = cv2.getTrackbarPos("S Low",  W)
        s_high     = cv2.getTrackbarPos("S High", W)
        v_low      = cv2.getTrackbarPos("V Low",  W)
        v_high     = cv2.getTrackbarPos("V High", W)
        if canny_low >= canny_high:
            canny_high = canny_low + 1

        rx, ry, rw, rh = roi
        level_y, vis, edge_vis, mask_vis = detect_liquid_level(
            frame[ry:ry+rh, rx:rx+rw],
            blur, canny_low, canny_high, top_m, bot_m,
            h_low, h_high, s_low, s_high, v_low, v_high, use_color
        )

        preview = frame.copy()
        cv2.rectangle(preview, (rx, ry), (rx+rw, ry+rh), (0, 255, 0), 2)
        if level_y is not None:
            cv2.line(preview, (rx, ry+level_y), (rx+rw, ry+level_y), (0, 255, 0), 2)
            print(f"\r[DEBUG] y={level_y}px  blur={blur} "
                  f"canny=({canny_low},{canny_high}) margin=({top_m}%,{bot_m}%) "
                  f"color={'on' if use_color else 'off'} "
                  f"HSV=({h_low}-{h_high},{s_low}-{s_high},{v_low}-{v_high})",
                  end="", flush=True)

        cv2.imshow("Camera",     preview)
        cv2.imshow("ROI",        vis)
        cv2.imshow("Edge Map",   edge_vis)
        cv2.imshow("Color Mask", mask_vis)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    print(f"\n\n── 复制以下参数到 detect.py ──")
    print(f"BLUR        = {blur}")
    print(f"CANNY_LOW   = {canny_low}")
    print(f"CANNY_HIGH  = {canny_high}")
    print(f"TOP_MARGIN  = {top_m}")
    print(f"BOT_MARGIN  = {bot_m}")
    print(f"USE_COLOR   = {use_color}")
    print(f"H_LOW, H_HIGH = {h_low}, {h_high}")
    print(f"S_LOW, S_HIGH = {s_low}, {s_high}")
    print(f"V_LOW, V_HIGH = {v_low}, {v_high}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
