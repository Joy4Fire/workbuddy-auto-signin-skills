# WorkBuddy Auto Sign-in Skill

Automated daily sign-in for **WorkBuddy** (腾讯云 CodeBuddy AI 助手桌面应用) on Windows.

## ✨ Features

- 🎯 **Adaptive Coordinates** - Uses percentage-based positioning, automatically adapts to different window sizes
- 🔍 **OpenCV Button Detection** - Automatically detects the "立即领取" button via image recognition
- 🪟 **Smart Window Management** - Handles minimized windows, multi-monitor setups
- 🔘 **Double-Click Trigger** - Correctly triggers sign-in (single click doesn't work!)
- 🐛 **Debug Mode** - Save screenshots at each step for troubleshooting

## 📦 Installation

### 1. Install as WorkBuddy Skill

Copy this skill to your WorkBuddy skills directory:

```bash
cp -r workbuddy-auto-signin ~/.workbuddy/skills/
```

### 2. Install Dependencies

```bash
pip install pyautogui pillow numpy opencv-python-headless
```

## 🚀 Usage

### Via WorkBuddy Skill System

Simply say: `签到`, `每日签到`, `WorkBuddy签到`, `自动领取积分`

### Run Directly

```bash
# Silent mode
python scripts/auto_signin.py

# Debug mode (save screenshots)
python scripts/auto_signin.py --debug

# Print current config
python scripts/auto_signin.py --save-config
```

## ⚙️ Configuration

Edit `config/signin_config.json`:

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

### Coordinate System

| Element | Position | Description |
|---------|----------|-------------|
| Avatar | 3.17% from left, 5.33% from bottom | Opens sign-in panel |
| Button | 8.58% from left, 51.67% from top | "立即领取" button |

**Adaptive**: Coordinates are percentage-based, so they automatically scale to any window size.

## 🔧 Troubleshooting

| Symptom | Cause | Fix |
|----------|-------|-----|
| `WorkBuddy window not found` | App not running | Start WorkBuddy first |
| Clicks wrong area | Window size changed | Run with `--debug`, check screenshots |
| Button found but no response | Not using double-click | Config has `click_method: "double"` |
| OpenCV finds nothing | UI layout changed | Update percentages in config |

## 📝 Technical Notes

- **Why double-click?** Single click only focuses the button, doesn't trigger sign-in
- **Why percentage coordinates?** Adapts to different window sizes and screen resolutions
- **Why OpenCV?** Electron apps don't expose UI elements to accessibility APIs

See `references/technical_notes.md` for detailed debugging history.

## 🖥️ Requirements

- Windows 10/11
- Python 3.11+
- WorkBuddy desktop app running
- Dependencies: pyautogui, Pillow, numpy, opencv-python-headless

## 📄 License

MIT
