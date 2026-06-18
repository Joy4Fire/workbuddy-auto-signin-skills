---
name: workbuddy-auto-signin
description: >
  Automate daily sign-in for WorkBuddy (腾讯云 CodeBuddy AI 助手) on Windows.
  Uses image recognition (OpenCV) and adaptive coordinate clicking.
  Trigger when user says: 签到, 每日签到, WorkBuddy签到, 自动领取积分, sign in, daily check-in.
license: MIT
version: 1.0.0
tags: [automation, windows, workbuddy, desktop-ui, opencv]
---

# WorkBuddy Auto Sign-in

Automated daily sign-in for **WorkBuddy** (腾讯云 CodeBuddy AI 助手桌面应用) on Windows using image recognition + adaptive coordinate clicking.

> ⚠️ **Windows only** — relies on Win32 APIs (`ctypes`), `pyautogui`, `PIL`, and OpenCV.

## When to Use

Use this skill when the user requests any of the following:
- 签到 / 每日签到
- WorkBuddy签到 / 自动领取积分
- sign in / daily check-in / claim daily rewards

## Setup

### Install Dependencies

```bash
pip install pyautogui pillow numpy opencv-python-headless
```

### Install Skill

Copy this skill to your WorkBuddy skills directory:

```bash
cp -r workbuddy-auto-signin ~/.workbuddy/skills/
```

Or install via WorkBuddy skill manager.

## How It Works

Since WorkBuddy is an **Electron app**, its internal DOM elements are not accessible via standard accessibility APIs. This skill uses a **visual approach**:

1. **Window Management**: Find WorkBuddy via Win32 `EnumWindows`, restore if minimized, move to primary monitor
2. **Panel Opening**: Click the user avatar (bottom-left sidebar) to open sign-in panel
3. **Button Detection**: Use **OpenCV grayscale thresholding (<120)** to detect the dark "立即领取" button. Falls back to percentage-based coordinates if detection fails
4. **Execution**: **Double-click** the button (single click does NOT trigger sign-in!)
5. **Verification**: Capture result screenshot; success shows "✅ 领取成功！获得 150 Credits" toast

## Usage

### Via WorkBuddy Conversation (Recommended)

Simply say:
```
签到
每日签到
WorkBuddy签到
自动领取积分
```

### Run Script Directly

```bash
# Silent mode
python scripts/auto_signin.py

# Debug mode (save screenshots to templates/)
python scripts/auto_signin.py --debug

# Print current config
python scripts/auto_signin.py --save-config
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
    "signin_button": {"x_percent": 0.0858, "y_percent": 0.5167}
})
```

## Configuration

Config file: `config/signin_config.json`

```json
{
  "avatar_click": {
    "x_percent": 0.0317,
    "y_from_bottom_percent": 0.0533
  },
  "signin_button": {
    "x_percent": 0.0858,
    "y_percent": 0.5167,
    "click_method": "double"
  }
}
```

### Adaptive Coordinates

Coordinates are **percentage-based** to adapt to different window sizes:

| Element | Position | Description |
|---------|----------|-------------|
| Avatar | 3.17% from left, 5.33% from bottom | Opens sign-in panel |
| Button | 8.58% from left, 51.67% from top | "立即领取" button |

## Troubleshooting

| Symptom | Cause | Fix |
|----------|-------|-----|
| `WorkBuddy window not found` | App not running | Start WorkBuddy first |
| Clicks wrong area | Window size changed | Run with `--debug`, check screenshots |
| Button found but no response | Not using double-click | Config has `click_method: "double"` |
| OpenCV finds nothing | UI layout changed | Update percentages in config |

## Quick Reference

| Task | Command |
|------|---------|
| Run sign-in | `python scripts/auto_signin.py` |
| Debug mode | `python scripts/auto_signin.py --debug` |
| View config | `python scripts/auto_signin.py --save-config` |
| Install deps | `pip install pyautogui pillow numpy opencv-python-headless` |

## File Structure

| File | Purpose |
|------|---------|
| `SKILL.md` | AI agent instruction document (trigger words, workflow) |
| `README.md` | Human-readable project documentation |
| `scripts/auto_signin.py` | Core sign-in script (adaptive coordinates) |
| `config/signin_config.json` | Coordinate configuration (percentage format) |
| `references/technical_notes.md` | Technical documentation (debug history) |
| `templates/` | Debug screenshot directory (gitignored) |

## Important Notes

- **Why double-click?** Single click only focuses the button, doesn't trigger sign-in
- **Why percentage coordinates?** Adapts to different window sizes and screen resolutions
- **Why OpenCV?** Electron apps don't expose UI elements to accessibility APIs

---

_This skill is not officially affiliated with WorkBuddy._
