#!/usr/bin/env python3
"""
WorkBuddy Auto Sign-in Helper v10 — Vision-Driven Edition

This script is a THIN HELPER for the agent-driven sign-in workflow.
It handles window management, screenshot capture, click execution,
and input testing — but does NOT do any UI element detection.

All "vision intelligence" (finding avatar, finding buttons, verifying
results) comes from the agent's multimodal capabilities via the Read tool.

Usage (CLI subcommands):
  python auto_signin.py find-window          # Find WorkBuddy HWND + rect
  python auto_signin.py activate HWND        # Activate & position window
  python auto_signin.py screenshot [output]  # Capture screenshot, save to file
  python auto_signin.py click X Y [method]   # Click at coords (single/double)
  python auto_signin.py press-key KEY        # Press a keyboard key
  python auto_signin.py check-lock           # Check if screen is locked
  python auto_signin.py wake-screen          # Wake display from sleep (Shift key)
  python auto_signin.py test-input           # Test if input simulation works
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
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except AttributeError:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

import pyautogui
from PIL import ImageGrab
import numpy as np

pyautogui.FAILSAFE = False

# ── Config ──────────────────────────────────────────────────────

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")

DEFAULT_CONFIG = {
    "window_position": {
        "width_percent": 0.6,
        "height_percent": 0.7,
        "x_percent": 0.2,
        "y_percent": 0.15,
    },
}


# ── Win32 Helpers ───────────────────────────────────────────────

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
    """Check if workstation is locked (Winlogon secure desktop)."""
    hDesk = user32.OpenInputDesktop(0, False, 0x80000000)
    if not hDesk:
        return True
    buf = ctypes.create_unicode_buffer(256)
    result = user32.GetUserObjectInformationW(hDesk, 2, buf, 256, None)
    user32.CloseDesktop(hDesk)
    if not result:
        return True
    return "Winlogon" in buf.value


def find_workbuddy_window():
    """Find the WorkBuddy IDE/chat window. This is the window that contains
    the daily sign-in panel (accessible via user avatar at bottom-left)."""
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    result = []

    def enum_cb(hwnd, _lp):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if "WorkBuddy" in buf.value:
                result.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    return result[0] if result else None


def get_rect(hwnd):
    """Get window rect as (left, top, right, bottom)."""
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def activate_window(hwnd):
    """Bring window to foreground, restore if minimized, position it."""
    config = load_config()
    win_pos = config.get("window_position", DEFAULT_CONFIG["window_position"])

    # Restore if minimized
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
    else:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.3)

    # Allow foreground window change
    try:
        user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
    except (AttributeError, OSError):
        pass

    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)

    # Position window for consistent screenshots
    screen_w, screen_h = get_screen_resolution()
    win_w = int(screen_w * win_pos.get("width_percent", 0.6))
    win_h = int(screen_h * win_pos.get("height_percent", 0.7))
    x = int(screen_w * win_pos.get("x_percent", 0.2))
    y = int(screen_h * win_pos.get("y_percent", 0.15))

    x = max(0, min(x, screen_w - win_w))
    y = max(0, min(y, screen_h - win_h))

    user32.SetWindowPos(hwnd, 0, x, y, win_w, win_h, 0)
    time.sleep(0.5)

    # Return final rect
    return get_rect(hwnd)


def take_screenshot(output_path, region=None):
    """Capture screenshot. If region=None, capture full screen.
    region format: (x1, y1, x2, y2) or 'x1,y1,x2,y2'
    """
    if region and isinstance(region, str):
        parts = [int(p) for p in region.split(",")]
        region = tuple(parts)

    if region:
        img = ImageGrab.grab(bbox=region)
    else:
        img = ImageGrab.grab()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path)

    if region:
        print(f"Screenshot saved: {output_path} [region: {region}]")
    else:
        print(f"Screenshot saved: {output_path} [full screen]")
    return output_path


def click_at(x, y, method="single"):
    """Click at screen coordinates. method: 'single' or 'double'."""
    x, y = int(x), int(y)
    print(f"Clicking at ({x}, {y}) [{method}-click]")
    if method == "double":
        pyautogui.doubleClick(x=x, y=y)
    else:
        pyautogui.click(x=x, y=y)


def press_key(key):
    """Press a keyboard key."""
    print(f"Pressing key: {key}")
    pyautogui.press(key)


def wake_screen():
    """
    Attempt to wake the display from sleep AND verify input simulation works.

    Strategy (avoids the false-positive of relying on Shift key visual side-effects):
    1. Find WorkBuddy window
    2. Activate it (this also wakes a sleeping display via any window-rendering change)
    3. Click the user avatar at bottom-left (this ALWAYS produces visual change if input works:
       either opens a panel, or at minimum moves the cursor over a button which gets hover state)
    4. Wait 2s, take screenshot, compare to baseline
    5. If change > 1%: input is working AND display is awake → success
    6. Press Escape to close any opened panel
    7. Minimize+restore as a final fallback to distinguish "input blocked" from "screenshot broken"

    Why this works: Shift key has near-zero visual side-effects in most UI states (no popover
    to close, no focus indicator), so 0% change from Shift doesn't mean input is blocked.
    Clicking the avatar is a definitive input test — if the panel doesn't open, the click
    didn't reach the window.
    """
    screen_w, screen_h = get_screen_resolution()

    # Find and activate WorkBuddy
    hwnd = find_workbuddy_window()
    if not hwnd:
        result = {
            "status": "window_not_found",
            "message": "WorkBuddy window not found. Cannot test input.",
            "screen_resolution": [int(screen_w), int(screen_h)],
        }
        print(json.dumps(result, ensure_ascii=False))
        return result

    rect = activate_window(hwnd)
    ww = rect[2] - rect[0]
    wh = rect[3] - rect[1]
    avatar_x = rect[0] + int(ww * 0.0317)   # 3.17% from left
    avatar_y = rect[1] + int(wh * 0.9467)   # 94.67% from top (5.33% from bottom)

    # Take baseline
    before = np.array(ImageGrab.grab())
    total_pixels = before.shape[0] * before.shape[1]

    # Click avatar — this is a guaranteed-visual-change test
    pyautogui.click(avatar_x, avatar_y)
    time.sleep(2.5)

    # Take after
    after = np.array(ImageGrab.grab())
    changed = np.sum(np.any(before != after, axis=2))
    click_change_pct = round(100.0 * float(changed) / max(float(total_pixels), 1), 2)

    # Close any panel that opened
    pyautogui.press("escape")
    time.sleep(0.5)

    # Fallback: minimize+restore to verify screenshots capture real changes
    before_min = np.array(ImageGrab.grab())
    user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
    time.sleep(0.5)
    after_min = np.array(ImageGrab.grab())
    changed_min = np.sum(np.any(before_min != after_min, axis=2))
    min_change_pct = round(100.0 * float(changed_min) / max(float(total_pixels), 1), 2)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.3)

    # Decision logic
    # click_change_pct > 1%: avatar click worked → display awake AND input working
    # click_change_pct < 1% AND min_change_pct > 5%: input blocked (session isolation)
    # click_change_pct < 1% AND min_change_pct < 1%: screenshots broken
    if click_change_pct > 1.0:
        status = "ok"
        message = f"Display is awake and input is working (avatar click produced {click_change_pct:.1f}% change)."
    elif click_change_pct < 1.0 and min_change_pct > 5.0:
        status = "input_blocked"
        message = f"Display is awake but input events are blocked (session isolation). Avatar click produced {click_change_pct:.1f}% change while window minimize registered {min_change_pct:.1f}%. This is a hard block — retrying won't help."
    elif click_change_pct < 1.0 and min_change_pct < 1.0:
        status = "screenshots_broken"
        message = f"Screenshots may not capture real screen content. Both avatar click ({click_change_pct:.1f}%) and window minimize ({min_change_pct:.1f}%) produced near-0% change."
    else:
        # Edge case: 0.5-1% from click — could be tiny UI repaint, treat as OK with warning
        status = "ok"
        message = f"Display is awake and input appears to be working (avatar click produced {click_change_pct:.1f}% change — minimal but non-zero)."

    result = {
        "status": status,
        "message": message,
        "avatar_click_change_pct": float(click_change_pct),
        "window_minimize_change_pct": float(min_change_pct),
        "screen_resolution": [int(screen_w), int(screen_h)],
        "hwnd_found": True,
    }

    print(json.dumps(result, ensure_ascii=False))
    return result


def test_input():
    """
    Test if input simulation is working. Strategy:
    1. Find & activate WorkBuddy window
    2. Take screenshot of window area
    3. Press Escape (should close any popover or produce visual change)
    4. Check pixel change within window area
    5. If no change, try minimize+restore to verify screenshots work
    
    Returns JSON with result.
    """
    screen_w, screen_h = get_screen_resolution()
    
    # Find and activate WorkBuddy
    hwnd = find_workbuddy_window()
    
    # Test 1: Press Escape within WorkBuddy window
    esc_change_pct = 0.0
    if hwnd:
        activate_window(hwnd)
        rect = get_rect(hwnd)
        # Capture window area only (more sensitive to small changes)
        before_win = np.array(ImageGrab.grab(bbox=rect))
        total_win = before_win.shape[0] * before_win.shape[1]
        
        pyautogui.press("escape")
        time.sleep(0.8)
        
        after_win = np.array(ImageGrab.grab(bbox=rect))
        changed_win = np.sum(np.any(before_win != after_win, axis=2))
        esc_change_pct = round(100.0 * float(changed_win) / max(float(total_win), 1), 2)
    
    # Test 2: Minimize + restore (verifies screenshots capture real changes)
    window_test_pct = 0.0
    if hwnd:
        before_full = np.array(ImageGrab.grab())
        total_full = before_full.shape[0] * before_full.shape[1]
        
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        time.sleep(0.5)
        after_full = np.array(ImageGrab.grab())
        changed_full = np.sum(np.any(before_full != after_full, axis=2))
        window_test_pct = round(100.0 * float(changed_full) / max(float(total_full), 1), 2)
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
    
    # Decision logic:
    # - If Escape produced ANY change (>0.1%) within window → input definitely works
    # - If Escape produced 0% but minimize/restore works → input MAY be blocked,
    #   but could also be that Escape just didn't do anything visually
    #   (no popover to close). This is a SOFT WARNING, not a hard abort.
    # - Proceed with actual flow regardless; verify with real screenshot comparison.
    input_confirmed = bool(esc_change_pct > 0.1)
    input_maybe_blocked = bool(esc_change_pct < 0.1 and window_test_pct > 5.0)
    
    result = {
        "esc_change_pct": float(esc_change_pct),
        "window_minimize_change_pct": float(window_test_pct),
        "input_confirmed": input_confirmed,
        "input_maybe_blocked": input_maybe_blocked,
        "screen_resolution": [int(screen_w), int(screen_h)],
        "hwnd_found": bool(hwnd is not None),
    }
    
    if input_maybe_blocked:
        result["warning"] = "Input simulation may be blocked (session isolation). Proceed with flow and verify via screenshot comparison."
    elif not input_confirmed and window_test_pct < 1.0:
        result["warning"] = "Screenshots may not be capturing real screen content."

    print(json.dumps(result, ensure_ascii=False))
    return result


def load_config():
    """Load config from JSON file."""
    config_path = os.path.join(CONFIG_DIR, "signin_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


# ── CLI Entry Point ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: auto_signin.py <command> [args]")
        print("Commands: find-window, activate, screenshot, click, press-key, check-lock, wake-screen, test-input")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "find-window":
        hwnd = find_workbuddy_window()
        if not hwnd:
            print(json.dumps({"status": "error", "message": "WorkBuddy not found"}, ensure_ascii=False))
            sys.exit(1)
        rect = get_rect(hwnd)
        print(json.dumps({
            "status": "ok",
            "hwnd": hwnd,
            "rect": list(rect),
            "screen": list(get_screen_resolution()),
        }, ensure_ascii=False))

    elif cmd == "activate":
        if len(sys.argv) < 3:
            print("Usage: auto_signin.py activate <HWND>")
            sys.exit(1)
        hwnd = int(sys.argv[2])
        rect = activate_window(hwnd)
        print(json.dumps({
            "status": "ok",
            "rect": list(rect),
        }, ensure_ascii=False))

    elif cmd == "screenshot":
        output = os.path.join(TEMPLATE_DIR, "screenshot.png")
        region = None
        # Parse args: --output path, --region x1,y1,x2,y2
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--output" and i + 1 < len(sys.argv):
                output = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--region" and i + 1 < len(sys.argv):
                region = sys.argv[i + 1]
                i += 2
            else:
                output = sys.argv[i]
                i += 1
        take_screenshot(output, region)

    elif cmd == "click":
        if len(sys.argv) < 4:
            print("Usage: auto_signin.py click <X> <Y> [single|double]")
            sys.exit(1)
        x, y = float(sys.argv[2]), float(sys.argv[3])
        method = sys.argv[4] if len(sys.argv) > 4 else "double"
        click_at(x, y, method)

    elif cmd == "press-key":
        if len(sys.argv) < 3:
            print("Usage: auto_signin.py press-key <KEY>")
            sys.exit(1)
        press_key(sys.argv[2])

    elif cmd == "wake-screen":
        wake_screen()

    elif cmd == "check-lock":
        locked = is_screen_locked()
        print(json.dumps({"screen_locked": locked}, ensure_ascii=False))

    elif cmd == "test-input":
        test_input()

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: find-window, activate, screenshot, click, press-key, check-lock, wake-screen, test-input")
        sys.exit(1)


if __name__ == "__main__":
    main()
