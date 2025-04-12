import time
import keyboard
import cv2
import numpy as np
import mss
import win32api
import win32gui
import win32con
import pygetwindow as gw

fish_game = False
fishing_active = False
mouse_held = False

window_rect = None

float_icon_template = cv2.imread("bobberIcons/bobber_icon1.png", cv2.IMREAD_UNCHANGED)
template_gray = cv2.cvtColor(float_icon_template, cv2.COLOR_BGR2GRAY)
template_w, template_h = template_gray.shape[::-1]

template_empty = cv2.imread('progressBar/progressTarget.png')
template_filled = cv2.imread('progressBar/progressTarget2.png')
template_smaller = cv2.imread('progressBar/progressTarget3.png')
template_indicator = cv2.imread('progressBar/Indicator.png')

def get_window_rect(window_title_substring):
    global window_rect

    if window_rect:
        return window_rect

    for window in gw.getWindowsWithTitle(''):
        if window_title_substring.lower() in window.title.lower():
            hwnd = window._hWnd
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"[!] Не удалось активировать окно: {e}")
            rect = win32gui.GetWindowRect(hwnd)
            window_rect = rect
            return rect
    return None


def capture_window(window_title_substring):
    rect = get_window_rect(window_title_substring)
    if rect:
        x1, y1, x2, y2 = rect
        width, height = x2 - x1, y2 - y1

        with mss.mss() as sct:
            monitor = {"top": y1, "left": x1, "width": width, "height": height}
            sct_img = sct.grab(monitor)

            img = np.array(sct_img, dtype=np.uint8)
            if img is None or img.size == 0:
                print("Ошибка: пустой кадр!")
                return None

            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
    return None

def toggle_fishing():
    global fishing_active
    fishing_active = not fishing_active
    print("Авто-рыбалка ВКЛ 🟢" if fishing_active else "Авто-рыбалка ВЫКЛ 🔴")

def restart_fishing():
    print("Перебрасываю удочку")
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def left_click():
    print("Начинаю мини игру")
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def detect_float_icon(frame):
    height, width = frame.shape[:2]

    roi_y_start = int(height * 0.84)
    roi_y_end = height
    roi_x_start = int(width * 0.76)
    roi_x_end = width

    roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    result = cv2.matchTemplate(gray_roi, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    return max_val > 0.7


def detect_fishing_bar(frame, template_empty, template_filled, template_indicator):
    height, width = frame.shape[:2]

    roi_y_start = int(height * 0.1)
    roi_y_end = int(height * 0.14)
    roi_x_start = int(width * 0.25)
    roi_x_end = int(width * 0.75)

    roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]

    result_indicator = cv2.matchTemplate(roi, template_indicator, cv2.TM_CCOEFF_NORMED)

    min_val_indicator, max_val_indicator, min_loc_indicator, max_loc_indicator = cv2.minMaxLoc(result_indicator)

    indicator_x = roi_x_start + max_loc_indicator[0] + template_indicator.shape[1] // 2
    indicator_width = template_indicator.shape[1] // 2


    result_empty = cv2.matchTemplate(roi, template_empty, cv2.TM_CCOEFF_NORMED)
    result_filled = cv2.matchTemplate(roi, template_filled, cv2.TM_CCOEFF_NORMED)

    min_val_empty, max_val_empty, min_loc_empty, max_loc_empty = cv2.minMaxLoc(result_empty)
    min_val_filled, max_val_filled, min_loc_filled, max_loc_filled = cv2.minMaxLoc(result_filled)

    if max_val_empty > max_val_filled:
            x, y = max_loc_empty
    else:
            x, y = max_loc_filled

    target_x = roi_x_start + x
    target_width = template_empty.shape[1]

    debug_image = roi.copy()

    cv2.rectangle(debug_image, (max_loc_indicator[0], max_loc_indicator[1]),
                  (max_loc_indicator[0] + template_indicator.shape[1],
                   max_loc_indicator[1] + template_indicator.shape[0]),
                  (0, 255, 0), 2)

    cv2.rectangle(debug_image, (x, y), (x + target_width, y + template_empty.shape[0]), (0, 215, 255), 2)

    cv2.imshow("DEBUG", debug_image)

    return {
        'indicator_x': indicator_x,
        'indicator_width': indicator_width,
        'target_x': target_x,
        'target_width': target_width,
        'roi_x_start': roi_x_start,
        'roi_x_end': roi_x_end
    }


def manage_fishing_minigame(frame):
    global mouse_held
    bar_data = detect_fishing_bar(frame, template_empty, template_filled, template_indicator)

    if not bar_data['indicator_width'] or not bar_data['target_width']:
        print("⚠️ Не удалось определить элементы шкалы рыбалки")
        return

    target_start = bar_data['target_x']
    target_end = bar_data['target_x'] + bar_data['target_width']

    indicator_start = bar_data['indicator_x']
    indicator_end = bar_data['indicator_x'] + bar_data['indicator_width']

    target_center = (target_start + target_end) / 2
    indicator_center = (indicator_start + indicator_end) / 2

    total_bar_width = bar_data['roi_x_end'] - bar_data['roi_x_start']

    offset = (indicator_center - target_center) / (total_bar_width * 0.5)

    threshold = 0.04

    if offset < -threshold:
        if not mouse_held:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            mouse_held = True
            print(f"⬆️ Нажимаем (offset={offset:.2f}) — индикатор левее центра")
    elif offset > threshold:
        if mouse_held:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            mouse_held = False
            print(f"⬇️ Отпускаем (offset={offset:.2f}) — индикатор правее центра")

    else:
        print(f"✅ В центре (offset={offset:.2f}) — ничего не делаем")

    debug_bar = np.zeros((50, total_bar_width, 3), dtype=np.uint8)

    # Рисуем шкалу
    cv2.rectangle(debug_bar, (0, 0), (total_bar_width, 50), (50, 50, 50), -1)

    relative_target_start = target_start - bar_data['roi_x_start']
    relative_target_width = bar_data['target_width']
    cv2.rectangle(debug_bar,
                  (relative_target_start, 0),
                  (relative_target_start + relative_target_width, 50),
                  (0, 255, 0), -1)

    relative_indicator_start = indicator_start - bar_data['roi_x_start']
    relative_indicator_width = bar_data['indicator_width']
    cv2.rectangle(debug_bar,
                  (relative_indicator_start, 0),
                  (relative_indicator_start + relative_indicator_width, 50),
                  (0, 165, 255), -1)

    cv2.imshow("Визуализация шкалы", debug_bar)


def detect_completion(frame):
    height, width = frame.shape[:2]

    roi_y_start = int(height * 0.4)
    roi_y_end = int(height * 0.6)
    roi_x_start = int(width * 0.3)
    roi_x_end = int(width * 0.7)

    roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    white_pixels = np.sum(thresh > 0)
    threshold = 3000
    return white_pixels > threshold

keyboard.add_hotkey("F6", toggle_fishing)
cv2.namedWindow("(Live)")

while True:
    current_frame = capture_window("Genshin Impact")
    if current_frame is None:
        print("Ошибка: не удалось захватить окно Genshin Impact.")
        continue

    if fishing_active:
        if not fish_game and detect_float_icon(current_frame):
            fish_game = True
            print("🎯 Обнаружен значок мини-игры!")
            left_click()
        elif fish_game:
            manage_fishing_minigame(current_frame)
            if detect_completion(current_frame):
                fish_game = False
                print("✅ Мини-игра завершена успешно!")
                time.sleep(5)
                restart_fishing()
                time.sleep(2)

    cv2.imshow("(Live)", current_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
