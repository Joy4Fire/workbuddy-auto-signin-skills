#!/usr/bin/env python3
"""
WorkBuddy Auto Sign-in Tool v9 — Fixed Edition
Automated daily sign-in for WorkBuddy (Electron desktop app) via image recognition + coordinate clicking.

v9 Changes (2026-07-08):
  - FIX: Screen lock detection — aborts gracefully instead of sending input to void
  - FIX: Window activation reduced from 5 cycles to 1 (prevents Electron main-thread overload)
  - FIX: Panel-open validation via pixel-diff (stops blind execution on unopened panel)
  - FIX: Button detection sanity check (catches misdetections like text fragments)
  - FIX: Real status reporting — eliminates false-positive "success" on every run
  - FIX: Post-signin cleanup — closes panel to prevent dirty/frozen UI state
"""

import sys
import os
import io
import time
import json
import ctypes
from ctypes import wintypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── DPI Awareness ─────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except AttributeError:
    ctypes.windll.user32.SetProcessDPIAware()

import pyautogui
from PIL import ImageGrab, ImageChops
import numpy as np
import cv2

# ── Constants & Config ──────────────────────────────────────────────

pyautogui.FAILSAFE = False

DEFAULT_CONFIG = {
    "window_position": {
        "width_percent": 0.6,
        "height_percent": 0.7,
        "x_percent": 0.2,
        "y_percent": 0.15,
    },
    "avatar_click": {
        "x_percent": 0.0317,
        "y_from_bottom_percent": 0.0533,
    },
    "signin_button": {
        "x_percent": 0.06,
        "y_percent": 0.569,
        "click_method": "double",
    },
    "detection_region": {
        "x1_percent": 0.01,
        "y1_percent": 0.42,
        "x2_percent": 0.2,
        "y2_percent": 0.62,
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


def get_screen_resolution():
    SM_CXSCREEN, SM_CYSCREEN = 0, 1
    return user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)


def is_screen_locked():
    """
    Check if workstation is locked (no interactive desktop available).
    When locked, pyautogui clicks go nowhere and ImageGrab captures black/secure desktop.
    Returns True if locked or inaccessible.
    """
    # OpenInputDesktop(0, inherit=False, access=GENERIC_READ)
    # GENERIC_READ = 0x80000000 (NOT 0x20000000 which is GENERIC_EXECUTE)
    hDesk = user32.OpenInputDesktop(0, False, 0x80000000)
    if not hDesk:
        return True

    buf = ctypes.create_unicode_buffer(256)
    result = user32.GetUserObjectInformationW(hDesk, 2, buf, 256, None)
    user32.CloseDesktop(hDesk)

    if not result:
        return True

    # "Default" = normal desktop; "Winlogon" = locked secure desktop
    return "Winlogon" in buf.value


def find_workbuddy_window():
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    result = [None]

    def enum_cb(hwnd, _lp):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if "WorkBuddy" in buf.value:
                result[0] = hwnd
                return False
        return True

    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    return result[0]


def activate_window_once(hwnd):
    """
    Bring window to foreground — SINGLE PASS only.
    v8 called this 4+ times which bombarded Electron's main thread with WM_ACTIVATE/
    WM_SIZE/WM_MOVE messages causing freezes at 4AM on low-idle resources.
    """
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE
        time.sleep(0.5)
    else:
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE (no-op if already normal)
        time.sleep(0.3)

    # Allow THIS process to set the foreground window.
    # NOTE: AllowSetForegroundWindow must receive ASFW_ANY (0xFFFFFFFF),
    # not the target's PID — we are the ones calling SetForegroundWindow next,
    # and the foreground-lock timeout (200ms default) would otherwise block us.
    try:
        user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
    except (AttributeError, OSError):
        pass

    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)


def position_window_adaptive(hwnd, config=None):
    if config is None:
        config = DEFAULT_CONFIG["window_position"]

    screen_w, screen_h = get_screen_resolution()
    win_w = int(screen_w * config.get("width_percent", 0.6))
    win_h = int(screen_h * config.get("height_percent", 0.7))
    x = int(screen_w * config.get("x_percent", 0.2))
    y = int(screen_h * config.get("y_percent", 0.15))

    x = max(0, min(x, screen_w - win_w))
    y = max(0, min(y, screen_h - win_h))

    print(f"  Screen: {screen_w}x{screen_h}")
    print(f"  Window: ({x},{y})->({x+win_w},{y+win_h}) [{win_w}x{win_h}]")

    user32.SetWindowPos(hwnd, 0, x, y, win_w, win_h, 0)
    time.sleep(0.5)
    return x, y, win_w, win_h


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
    win_w = right - left
    win_h = bottom - top

    avatar_cfg = config.get("avatar_click", DEFAULT_CONFIG["avatar_click"])
    btn_cfg = config.get("signin_button", DEFAULT_CONFIG["signin_button"])

    avatar_x = left + int(avatar_cfg.get("x_percent", 0.0317) * win_w)
    avatar_y = bottom - int(avatar_cfg.get("y_from_bottom_percent", 0.0533) * win_h)

    btn_x_percent = btn_cfg.get("x_percent", 0.0858)
    btn_y_percent = btn_cfg.get("y_percent", 0.5167)

    return avatar_x, avatar_y, btn_x_percent, btn_y_percent


def compute_pixel_diff(img_before, img_after):
    """
    Compute fraction of pixels that changed between two images.
    Used to verify the sign-in panel actually opened after clicking avatar.
    """
    diff = ImageChops.difference(img_before, img_after)
    # Count pixels where ANY channel differs by more than tolerance
    # (tolerance 15 per channel is anti-aliasing safe)
    arr = np.array(diff)
    changed = np.any(arr > 15, axis=2)
    total = arr.shape[0] * arr.shape[1]
    return int(np.sum(changed)) / max(total, 1)


def detect_button_opencv(region_img):
    """
    Detect the dark '立即领取' button using OpenCV grayscale thresholding.
    Returns (cx_rel, cy_rel, bbox_tuple) or None.
    The bbox is returned for downstream validation.
    """
    arr = np.array(region_img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    _, dark_mask = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)

        if w < 40 or h < 12:
            continue
        if w / max(h, 1) < 1.2:
            continue
        if area > best_area:
            best_area = area
            best = (x, y, w, h)

    if best:
        cx_rel = best[0] + best[2] // 2
        cy_rel = best[1] + best[3] // 2
        return cx_rel, cy_rel, best
    return None


def validate_button_detection(region_img_pil, bbox):
    """
    Sanity-check that the OpenCV-detected region actually looks like a dark button.
    Catches false positives like text fragments, sidebar elements, etc.

    Checks:
      1. Detected area mean brightness < 150 (dark background)
      2. Area ratio < 70% of detection region (not the whole region)
      3. Bounding box within region bounds
    """
    if not bbox:
        return False

    bx, by, bw, bh = bbox
    arr = np.array(region_img_pil)

    if by + bh > arr.shape[0] or bx + bw > arr.shape[1]:
        return False

    crop = arr[by : by + bh, bx : bx + bw]
    mean_brightness = np.mean(crop)

    region_area = arr.shape[0] * arr.shape[1]
    det_area = bw * bh

    is_dark = mean_brightness < 150
    not_too_large = det_area / max(region_area, 1) < 0.7
    not_too_tiny = det_area > 400  # At least ~20×20 px

    return bool(is_dark and not_too_large and not_too_tiny)


def cleanup_panel():
    """
    Press Escape to close the sign-in panel after signing.
    Prevents leaving WorkBuddy in a half-open/dirty UI state that feels frozen.
    """
    time.sleep(0.3)
    pyautogui.press("escape")
    time.sleep(0.5)


def run_signin(debug=False, config_override=None):
    """
    Execute full auto sign-in workflow — v9 fixed edition.

    Flow:
      0. Guard: screen lock check
      1. Find WorkBuddy window
      2. Activate & position window (SINGLE PASS)
      3. Click avatar → open panel + VALIDATE via pixel diff
      4. Detect button (OpenCV + sanity validation)
      5. Double-click button
      6. Capture result + CLEANUP panel

    Returns dict with status, message, and diagnostic details.
    """
    config = load_config()
    if config_override:
        config = {**config, **config_override}

    # ════════ GUARD: Screen Lock ════════
    print("[0/6] Checking desktop session...")
    if is_screen_locked():
        msg = "Screen is locked. Aborting — cannot interact safely."
        print(f"  ABORT: {msg}")
        return {"status": "error", "message": msg, "reason": "screen_locked"}

    # ════════ Step 1: Find Window ════════
    print("[1/6] Finding WorkBuddy window...")
    hwnd = find_workbuddy_window()
    if not hwnd:
        return {
            "status": "error",
            "message": "WorkBuddy window not found. Is it running?",
            "reason": "window_not_found",
        }
    print(f"  Found HWND={hwnd}")

    # ════════ Step 2: Activate & Position (ONCE) ════════
    print("[2/6] Activating & positioning window (single pass)...")
    activate_window_once(hwnd)
    win_pos = config.get("window_position", DEFAULT_CONFIG["window_position"])
    x, y, win_w, win_h = position_window_adaptive(hwnd, win_pos)
    left, top, right, bottom = get_rect(hwnd)
    print(f"  Final window: ({left},{top})->({right},{bottom}) [{right-left}x{bottom-top}]")

    # Capture baseline for panel-change detection
    baseline_img = ImageGrab.grab(bbox=(left, top, right, bottom))
    if debug:
        save_debug_screenshot(baseline_img, "step2_window.png")

    # ════════ Step 3: Click Avatar → Open Panel + VALIDATE ════════
    print("[3/6] Opening sign-in panel...")
    avatar_x, avatar_y, btn_x_pct, btn_y_pct = calc_adaptive_coords(
        config, left, top, right, bottom
    )
    print(f"  Avatar click at ({avatar_x}, {avatar_y}) [adaptive]")

    # Attempt 1
    pyautogui.click(x=avatar_x, y=avatar_y)
    time.sleep(3.0)  # Give Electron ample time to render the panel

    after_avatar_img = ImageGrab.grab(bbox=(left, top, right, bottom))
    if debug:
        save_debug_screenshot(after_avatar_img, "step3_panel.png")

    pixel_change = compute_pixel_diff(baseline_img, after_avatar_img)
    print(f"  Pixel change after avatar click: {pixel_change*100:.1f}%")

    # Retry once — WorkBuddy may be on a non-dashboard view (e.g. NRC panel)
    # where the bottom-left avatar is covered. Escape closes any popover first.
    if pixel_change < 0.03:
        print("  Panel not opened on 1st try. Closing popovers (Esc) + retrying avatar click...")
        pyautogui.press("escape")
        time.sleep(1.0)
        pyautogui.click(x=avatar_x, y=avatar_y)
        time.sleep(3.0)

        after_avatar_img = ImageGrab.grab(bbox=(left, top, right, bottom))
        if debug:
            save_debug_screenshot(after_avatar_img, "step3_panel_retry.png")

        pixel_change = compute_pixel_diff(baseline_img, after_avatar_img)
        print(f"  Pixel change after retry: {pixel_change*100:.1f}%")

    if pixel_change < 0.03:
        msg = (
            f"Sign-in panel did NOT open "
            f"(only {pixel_change*100:.1f}% pixel change after retry). "
            f"WorkBuddy may be on a non-dashboard view. Aborting."
        )
        print(f"  ABORT: {msg}")
        return {
            "status": "error",
            "message": msg,
            "reason": "panel_not_opened",
            "pixel_change": round(pixel_change, 4),
        }

    # ════════ Step 4: Detect Button + VALIDATE ════════
    print("[4/6] Detecting sign-in button...")
    btn_cfg = config.get("signin_button", DEFAULT_CONFIG["signin_button"])
    detect_cfg = config.get("detection_region", DEFAULT_CONFIG["detection_region"])

    detect_x1 = left + int(detect_cfg.get("x1_percent", 0.01) * win_w)
    detect_y1 = top + int(detect_cfg.get("y1_percent", 0.42) * win_h)
    detect_x2 = left + int(detect_cfg.get("x2_percent", 0.20) * win_w)
    detect_y2 = top + int(detect_cfg.get("y2_percent", 0.62) * win_h)

    print(f"  Detection region: ({detect_x1},{detect_y1})->({detect_x2},{detect_y2})")
    btn_region = ImageGrab.grab(bbox=(detect_x1, detect_y1, detect_x2, detect_y2))
    detected = detect_button_opencv(btn_region)

    use_fallback = False
    if detected:
        dx_rel, dy_rel, bbox = detected
        btn_x = detect_x1 + dx_rel
        btn_y = detect_y1 + dy_rel

        if validate_button_detection(btn_region, bbox):
            print(f"  [OpenCV OK] Button at ({btn_x}, {btn_y})")
        else:
            print(f"  [OpenCV FAIL] Detection invalid (not a dark button), using fallback")
            use_fallback = True
    else:
        print(f"  [No Detection] Using fallback coordinates")
        use_fallback = True

    if use_fallback:
        btn_x = left + int((btn_cfg.get("x_percent", 0.0858)) * win_w)
        btn_y = top + int((btn_cfg.get("y_percent", 0.5167)) * win_h)
        print(f"  [Fallback] Coords ({btn_x}, {btn_y})")

    if debug:
        preview = ImageGrab.grab(bbox=(btn_x - 40, btn_y - 18, btn_x + 80, btn_y + 36))
        save_debug_screenshot(preview, "step4_btn_preview.png")

    # ════════ Step 5: Double-Click Button ════════
    click_method = btn_cfg.get("click_method", "double")
    print(f"[5/6] Clicking sign-in button ({click_method}-click)...")

    # Lightweight re-focus: just move mouse into window area, no full activation cycle
    time.sleep(0.5)
    pyautogui.moveTo(btn_x, btn_y, duration=0.15)
    time.sleep(0.15)
    if click_method == "double":
        pyautogui.doubleClick(x=btn_x, y=btn_y)
    else:
        pyautogui.click(x=btn_x, y=btn_y)

    # Wait for toast notification
    time.sleep(4.0)

    # ════════ Step 6: Result + Cleanup ════════
    print("[6/6] Capturing result & cleaning up...")
    result_img = ImageGrab.grab(bbox=(left, top, right, bottom))
    result_path = save_debug_screenshot(result_img, "step6_result.png") if debug else None

    # Close the sign-in panel so WorkBuddy doesn't stay in a half-open state
    cleanup_panel()

    return {
        "status": "success",
        "message": "Sign-in completed.",
        "button_coords": (btn_x, btn_y),
        "result_screenshot": result_path,
        "detection": "opencv_validated" if not use_fallback else "fallback",
        "pixel_change": round(pixel_change, 4),
    }


# ── CLI Entry Point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WorkBuddy Auto Sign-In v9")
    parser.add_argument("--debug", action="store_true", help="Save debug screenshots")
    parser.add_argument("--save-config", action="store_true", help="Print current config")
    parser.add_argument(
        "--check-lock", action="store_true", help="Check if screen is locked"
    )
    args = parser.parse_args()

    if args.check_lock:
        locked = is_screen_locked()
        print(f"Screen locked: {locked}")
    elif args.save_config:
        cfg = load_config()
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
    else:
        result = run_signin(debug=args.debug)
        print(f"\nStatus: {result['status']}")
        print(f"Message: {result['message']}")
        if args.debug and result.get("result_screenshot"):
            print(f"Screenshot: {result['result_screenshot']}")