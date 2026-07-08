---
name: workbuddy-auto-signin
description: >
  Automate daily sign-in for WorkBuddy (腾讯云 CodeBuddy AI 助手) on Windows.
  Uses image recognition (OpenCV) and adaptive coordinate clicking.
  Auto-adapts to different screen resolutions and window sizes.
  v9.2 freeze-fix edition: includes a screen-lock guard, panel-open pixel-diff
  validation with one retry, OpenCV button sanity-check, real error status
  reporting (no false positives), and post-signin panel cleanup.
  Trigger when user says: 签到, 每日签到, WorkBuddy签到, 自动领取积分, sign in, daily check-in.
license: MIT
version: 9.2.0
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

## How It Works (v9.2)

Since WorkBuddy is an **Electron app**, its internal DOM elements are not accessible via standard accessibility APIs. This skill uses a **visual approach** with multiple safety guards added in v9.2 to prevent the "frozen WorkBuddy" problem seen in earlier versions:

0. **Screen-lock guard** — Before any interaction, check the active desktop via `OpenInputDesktop`. If the session is locked (Winlogon secure desktop), abort immediately so no clicks are sent into the void.
1. **Window Management** — Find WorkBuddy via Win32 `EnumWindows`, restore if minimized, move to primary monitor. Window activation is done **once** (older versions hammered the Electron main thread with 5 activation cycles, causing freezes).
2. **Panel Opening + Validation** — Click the user avatar (bottom-left sidebar) to open the sign-in panel, then **verify the panel actually opened** by comparing screenshot pixels. A real panel open changes ≥3% of pixels; if it didn't open, press `Escape` and retry the avatar click once. Abort if it still didn't open (WorkBuddy may be on a non-dashboard view such as the NRC panel).
3. **Button Detection** — Use **OpenCV grayscale thresholding (<120)** to detect the dark "立即领取" button inside the green card. A **sanity check** (dark background, reasonable size/aspect) filters out misdetections like text fragments. Falls back to percentage-based coordinates if detection fails or is invalid.
4. **Execution** — **Double-click** the button (single click does NOT trigger sign-in!)
5. **Result + Cleanup** — Capture a result screenshot, then press `Escape` to **close the panel** so WorkBuddy isn't left in a half-open / apparently-frozen state.

### Status & Reliability

The script returns a JSON dict. **`status` is `success` or `error` — there are no silent false positives anymore.**

- `"status": "success"` → the panel opened and the double-click sequence ran. *Note:* this confirms the UI interaction completed; it does not OCR-verify the "领取成功" toast.
- `"status": "error"` with a `reason` code → the script aborted safely **without** clicking a wrong target:
  - `"screen_locked"` — PC is on the lock screen; run while logged in.
  - `"panel_not_opened"` — avatar click didn't open the panel (likely a non-dashboard view); switch to the main dashboard and re-run.
  - `"window_not_found"` — WorkBuddy isn't running.

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

# Only check whether the screen is locked (no clicks)
python scripts/auto_signin.py --check-lock
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
    "signin_button": {"x_percent": 0.06, "y_percent": 0.569}
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
    "x_percent": 0.06,
    "y_percent": 0.569,
    "click_method": "double"
  }
}
```

### Adaptive Coordinates

Coordinates are **percentage-based** to adapt to different window sizes:

| Element | Position | Description |
|---------|----------|-------------|
| Avatar | 3.17% from left, 5.33% from bottom | Opens sign-in panel |
| Button | 6.00% from left, 56.90% from top | "立即领取" button |

## Troubleshooting

| Symptom | Cause | Fix |
|----------|-------|-----|
| `WorkBuddy window not found` | App not running | Start WorkBuddy first |
| `reason: screen_locked` | PC is on the lock screen | Unlock / run while logged in |
| `reason: panel_not_opened` | WorkBuddy on a non-dashboard view (e.g. NRC panel) | Switch to the main dashboard, re-run |
| Clicks wrong area | Window size changed | Run with `--debug`, check screenshots |
| Button found but no response | Not using double-click | Config has `click_method: "double"` |
| OpenCV finds nothing / invalid | UI layout changed | Update percentages in config |

## Quick Reference

| Task | Command |
|------|---------|
| Run sign-in | `python scripts/auto_signin.py` |
| Debug mode | `python scripts/auto_signin.py --debug` |
| View config | `python scripts/auto_signin.py --save-config` |
| Check screen lock | `python scripts/auto_signin.py --check-lock` |
| Install deps | `pip install pyautogui pillow numpy opencv-python-headless` |

## File Structure

| File | Purpose |
|------|---------|
| `SKILL.md` | AI agent instruction document (trigger words, workflow) |
| `README.md` | Human-readable project documentation |
| `scripts/auto_signin.py` | Core sign-in script (v9.2 adaptive + safety guards) |
| `config/signin_config.json` | Coordinate configuration (percentage format) |
| `references/technical_notes.md` | Technical documentation (debug history, freeze-fix analysis) |
| `debug_enum.py` | Helper to enumerate WorkBuddy windows/PIDs for diagnosis |
| `templates/` | Debug screenshot directory (gitignored) |

## Important Notes

- **Why double-click?** Single click only focuses the button, doesn't trigger sign-in
- **Why percentage coordinates?** Adapts to different window sizes and screen resolutions
- **Why OpenCV?** Electron apps don't expose UI elements to accessibility APIs
- **Why the screen-lock guard?** At 4AM the PC may be locked; without it, clicks go nowhere and `ImageGrab` captures the secure desktop
- **Why pixel-diff validation?** Older versions double-clicked even when the panel never opened, hitting wrong UI and leaving WorkBuddy frozen. v9.2 aborts instead.
- **Why panel cleanup?** Leaving the sign-in popover open made WorkBuddy look frozen; `Escape` closes it cleanly.

---

_This skill is not officially affiliated with WorkBuddy._
