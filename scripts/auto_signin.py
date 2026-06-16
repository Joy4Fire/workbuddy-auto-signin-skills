#!/usr/bin/env python3
"""
WorkBuddy Auto Sign-in Tool
Automated daily sign-in for WorkBuddy (Electron desktop app) via image recognition + coordinate clicking.
Supports adaptive coordinate scaling for different window sizes.
"""

import sys
import os
import io
import time
import json
import ctypes
from ctypes import wintypes

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pyautogui
from PIL import ImageGrab
import numpy as np
import cv2

# ── Constants & Config ──────────────────────────────────────────────

pyautogui.FAILSAFE = False  # Prevent corner-triggered failsafe

DEFAULT_CONFIG = {
    "window_position": {"x": 340, "y": 50, "width": 1200, "height": 900},
    "avatar_click": {
        "x_percent": 0.0317,
        "y_from_bottom_percent": 0.0533,
    },
    "signin_button": {
        "x_percent": 0.0858,
        "y_percent": 0.5167,
        "click_method": "double",
    },
    "detection_region": {
        "x1_percent": 0.05,
        "y1_percent": 0.467,
        "x2_percent": 0.15,
        "y2_percent": 0.567,
    },
}

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")

# ── Win32 Helpers ───────────────────────────────────────────────────

user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def find_workbuddy_window():
    """Find WorkBuddy window by title."""
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
    )
    result = [None]

    def enum_cb(hwnd, _lp):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if "WorkBuddy" in buf.value and user32.IsWindowVisible(hwnd):
                result[0] = hwnd
                return False
        return True

    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    return result[0]


def activate_window(hwnd):
    """Bring window to foreground (handles minimized state)."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.3)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)


def position_window(hwnd, x=340, y=50, w=1200, h=900):
    """Move/resize window to specified position on primary monitor."""
    user32.SetWindowPos(hwnd, 0, x, y, w, h, 0)
    time.sleep(0.5)


def get_rect(hwnd):
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


# ── Core Logic ───────────────────────────────────────────────────────

def load_config():
    config_path = os.path.join(CONFIG_DIR, "signin_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


def save_debug_screenshot(img, name):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    path = os.path.join(TEMPLATE_DIR, name)
    img.save(path)
    print(f"  [debug] {path}")
    return path


def calc_adaptive_coords(config, left, top, right, bottom):
    """
    Calculate adaptive coordinates based on window size.
    Uses percentage-based positioning for adaptability across different screen resolutions.
    
    Returns: (avatar_x, avatar_y, btn_x_percent, btn_y_percent)
    """
    win_w = right - left
    win_h = bottom - top
    
    avatar_cfg = config.get("avatar_click", DEFAULT_CONFIG["avatar_click"])
    btn_cfg = config.get("signin_button", DEFAULT_CONFIG["signin_button"])
    
    # Avatar: percentage from left and bottom
    avatar_x = left + int(avatar_cfg.get("x_percent", 0.0317) * win_w)
    avatar_y = bottom - int(avatar_cfg.get("y_from_bottom_percent", 0.0533) * win_h)
    
    # Button: percentage from left and top
    btn_x_percent = btn_cfg.get("x_percent", 0.0858)
    btn_y_percent = btn_cfg.get("y_percent", 0.5167)
    
    return avatar_x, avatar_y, btn_x_percent, btn_y_percent


def detect_button_opencv(region_img):
    """
    Detect the dark '立即领取' button in the green card region using OpenCV.

    Strategy: threshold grayscale at <120 to find dark regions, then filter by
    shape (horizontal rectangle ~30-50% of region width × 20-40% of region height).
    Returns relative coordinates within region, or None.
    """
    arr = np.array(region_img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    _, dark_mask = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6))
    dark_mask = cv2.dilate(dark_mask, kernel, iterations=1)

    contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_fill = 0

    region_h, region_w = arr.shape[:2]
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)

        # Scale-invariant: filter by relative size to region
        if w < region_w * 0.3 or h < region_h * 0.2:
            continue
        
        # Aspect ratio: button should be wider than tall
        if w < h:
            continue

        fill_ratio = area / (w * h)
        if fill_ratio > best_fill:
            best_fill = fill_ratio
            best = (x, y, w, h)

    if best:
        cx_rel = best[0] + best[2] // 2
        cy_rel = best[1] + best[3] // 2
        return cx_rel, cy_rel
    return None


def run_signin(debug=False, config_override=None):
    """
    Execute full auto sign-in workflow with adaptive coordinate scaling.

    Steps:
      1. Find WorkBuddy window
      2. Activate & position window on primary monitor
      3. Click user avatar → open sign-in panel
      4. Detect '立即领取' button (OpenCV or fallback to percentage coords)
      5. Double-click the button
      6. Capture result screenshot

    Args:
        debug: If True, save intermediate screenshots.
        config_override: Optional dict to merge into loaded config.

    Returns:
        dict with status, message, and optional result screenshot path.
    """
    config = load_config()
    if config_override:
        config = {**config, **config_override}

    # Step 1: Find window
    print("[1/6] Finding WorkBuddy window...")
    hwnd = find_workbuddy_window()
    if not hwnd:
        return {"status": "error", "message": "WorkBuddy window not found. Is it running?"}
    print(f"  Found HWND={hwnd}")

    # Step 2: Activate & position
    print("[2/6] Activating & positioning window...")
    activate_window(hwnd)
    position_window(hwnd)
    activate_window(hwnd)
    left, top, right, bottom = get_rect(hwnd)
    win_w, win_h = right - left, bottom - top
    print(f"  Window: ({left},{top})->({right},{bottom}) [{win_w}x{win_h}]")

    if debug:
        win_img = ImageGrab.grab(bbox=(left, top, right, bottom))
        save_debug_screenshot(win_img, "step2_window.png")

    # Step 3: Click avatar to open panel (adaptive coordinates)
    print("[3/6] Opening sign-in panel...")
    avatar_x, avatar_y, btn_x_pct, btn_y_pct = calc_adaptive_coords(
        config, left, top, right, bottom
    )
    print(f"  Avatar click at ({avatar_x}, {avatar_y}) [adaptive]")
    pyautogui.click(x=avatar_x, y=avatar_y)
    time.sleep(2.5)
    activate_window(hwnd)
    time.sleep(0.5)

    if debug:
        panel_img = ImageGrab.grab(bbox=(left, top, right, bottom))
        save_debug_screenshot(panel_img, "step3_panel.png")

    # Step 4: Detect button (adaptive region)
    print("[4/6] Detecting sign-in button...")
    btn_cfg = config.get("signin_button", DEFAULT_CONFIG["signin_button"])
    detect_cfg = config.get("detection_region", DEFAULT_CONFIG["detection_region"])

    # Adaptive detection region (percentage-based)
    detect_x1 = left + int(detect_cfg.get("x1_percent", 0.05) * win_w)
    detect_y1 = top + int(detect_cfg.get("y1_percent", 0.467) * win_h)
    detect_x2 = left + int(detect_cfg.get("x2_percent", 0.15) * win_w)
    detect_y2 = top + int(detect_cfg.get("y2_percent", 0.567) * win_h)
    
    print(f"  Detection region: ({detect_x1},{detect_y1})->({detect_x2},{detect_y2})")
    btn_region = ImageGrab.grab(bbox=(detect_x1, detect_y1, detect_x2, detect_y2))
    detected = detect_button_opencv(btn_region)

    if detected:
        dx_rel, dy_rel = detected
        btn_x = detect_x1 + dx_rel
        btn_y = detect_y1 + dy_rel
        print(f"  [OpenCV] Detected button center at ({btn_x}, {btn_y})")
    else:
        # Fallback to percentage-based coordinates
        btn_x = left + int(btn_x_pct * win_w)
        btn_y = top + int(btn_y_pct * win_h)
        print(f"  [Fallback] Using percentage coords ({btn_x}, {btn_y})")

    if debug:
        preview = ImageGrab.grab(bbox=(btn_x - 40, btn_y - 18, btn_x + 80, btn_y + 36))
        save_debug_screenshot(preview, "step4_btn_preview.png")

    # Step 5: Click button (must be double-click!)
    click_method = btn_cfg.get("click_method", "double")
    print(f"[5/6] Clicking sign-in button ({click_method}-click)...")
    if click_method == "double":
        pyautogui.doubleClick(x=btn_x, y=btn_y)
    else:
        pyautogui.click(x=btn_x, y=btn_y)
    time.sleep(4)

    # Step 6: Result
    print("[6/6] Capturing result...")
    result_img = ImageGrab.grab(bbox=(left, top, right, bottom))
    result_path = save_debug_screenshot(result_img, "step6_result.png") if debug else None

    return {
        "status": "success",
        "message": "Sign-in flow completed. Check result screenshot for confirmation.",
        "button_coords": (btn_x, btn_y),
        "result_screenshot": result_path,
    }


# ── CLI Entry Point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WorkBuddy Auto Sign-In")
    parser.add_argument("--debug", action="store_true", help="Save debug screenshots")
    parser.add_argument("--save-config", action="store_true", help="Print current config for saving")
    args = parser.parse_args()

    if args.save_config:
        cfg = load_config()
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
    else:
        result = run_signin(debug=args.debug)
        print(f"\nStatus: {result['status']}")
        print(f"Message: {result['message']}")
        if args.debug and result.get("result_screenshot"):
            print(f"Screenshot: {result['result_screenshot']}")
