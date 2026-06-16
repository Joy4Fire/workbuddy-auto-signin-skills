---
name: workbuddy-auto-signin
description: >
  This skill should be used when users need to automatically sign in to WorkBuddy
  (腾讯云 CodeBuddy AI 助手桌面应用) on Windows. Handles window management,
  UI automation via image recognition (OpenCV), and coordinate-based clicking.
  Trigger keywords: 自动签到, 每日签到, WorkBuddy签到, 自动领取积分.
agent_created: true
version: 1.0.0
tags: [automation, windows, workbuddy, desktop-ui]
---

# WorkBuddy Auto Sign-in

Automated daily sign-in for **WorkBuddy** (Electron desktop app) using image recognition + coordinate clicking.

> ⚠️ **Windows only** — relies on Win32 APIs (`ctypes.windll.user32`), `pyautogui`, `PIL`, and OpenCV.

## Prerequisites

| Dependency | Purpose | Install |
|---|---|---|
| Python 3.11+ | Runtime | Managed runtime preferred |
| pyautogui | Mouse/keyboard control | Pre-installed in managed env |
| Pillow (`PIL`) | Screen capture | Pre-installed in managed env |
| numpy + opencv-python | Image analysis / button detection | Install if missing |
| ctypes (stdlib) | Win32 API calls | Built-in |

Check/install dependencies:

```bash
pip install pyautogui pillow numpy opencv-python-headless
```

## How It Works

Since WorkBuddy is an **Electron app**, its internal DOM elements are not accessible via standard accessibility APIs (pywinauto UIA sees only a `Chrome Legacy Window`). The skill uses a **visual approach**:

1. **Window Management**: Find WorkBuddy via Win32 `EnumWindows`, restore if minimized, move to primary monitor at known coordinates `(340,50)→(1540,950)`.
2. **Panel Opening**: Click the user avatar (bottom-left sidebar) to pop up the sign-in panel.
3. **Button Detection**: Use **OpenCV grayscale thresholding (<120)** to detect the dark "立即领取" button within the green card region. Falls back to saved coordinates if detection fails.
4. **Execution**: **Double-click** the button (single click does NOT trigger sign-in!).
5. **Verification**: Capture result screenshot; success shows "✅ 领取成功！获得 150 Credits" toast.

## Execution

Run the script directly:

```bash
python scripts/auto_signin.py --debug    # with debug screenshots
python scripts/auto_signin.py             # silent mode
python scripts/auto_signin.py --save-config  # print current config
```

### Programmatic Usage

```python
from scripts.auto_signin import run_signin, load_config

# Run sign-in
result = run_signin(debug=True)
print(result["status"])      # "success" or "error"
print(result["message"])

# Override coordinates dynamically:
result = run_signin(config_override={
    "signin_button": {"x_offset": 103, "y_offset": 465}
})
```

## Configuration

Config file: `<skill-dir>/config/signin_config.json`

```json
{
  "window_position": { "x": 340, "y": 50, "width": 1200, "height": 900 },
  "avatar_click": { "x_offset": 38, "y_from_bottom": 48 },
  "signin_button": {
    "x_offset": 103,
    "y_offset": 465,
    "click_method": "double"
  }
}
```

### Coordinate Reference (window at 340,50 → 1540,950, size 1200×900)

| Element | Absolute | Relative to Window | Notes |
|---|---|---|---|
| User avatar | (378, 902) | (+38, -48) | Opens sign-in panel |
| **Sign-in button** | **(443, 515)** | **(+103, +465)** | Must double-click! |

### Adaptability

If WorkBuddy updates its UI layout:

1. Run with `--debug` to get screenshots at each step.
2. Inspect `templates/step3_panel.png` to find new button location.
3. Update `signin_config.json` coordinates.
4. Or let OpenCV auto-detect (works for dark buttons in the green card region).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FailSafeException: mouse moving to corner` | Window minimized → coords = (-32000,-32000) | Code handles this via `IsIconic()` check |
| Clicks "退出登录" instead of sign-in | Y-coordinate too low (near bottom of panel) | Check config y_offset; button is in green card (~top+465), not panel bottom |
| Button found but no response | Single-click used | **Must use `doubleClick()`** — single click only focuses |
| Panel doesn't open after avatar click | Window lost focus / avatar coord shifted | Ensure `SetForegroundWindow()` called before click; verify avatar offset |
| OpenCV finds nothing | Button color changed or panel not open | Verify panel is visible; fall back to manual coords in config |

## Key Technical Notes

- See `references/technical_notes.md` for detailed debugging history and pixel-mapping discoveries.
