# Technical Notes — WorkBuddy Auto Sign-in

## Debugging History & Discoveries

This document records key findings from extensive pixel-level debugging sessions (v3 → v14 → run3).

### UI Layout Mapping (Absolute coords, window at 340,50 → 1540,950)

```
Y Range          | UI Element
-----------------|-----------------------------------
~326            | "体验版" label text
~370            | "Buddy 加油站" card title
~410–470        | Green card content (本期, 积分 info)
~497–530        | 🎯 "立即领取 ▼" dark button + "体验Ima →" light button
~530+           | 积分余额, 成长计划, 设置, 外观, 帮助, 退出登录
```

### Critical Discoveries

1. **Double-click required**
   - `pyautogui.click()` → button gets focus but does **NOT** trigger sign-in
   - `pyautogui.doubleClick()` → ✅ "领取成功！获得 150 Credits"

2. **Button is dark, not light**
   - Initial assumption: "立即领取" was a white/light-colored button → wrong
   - Actual: Dark gray/black rounded rectangle with white text inside green card
   - HSV color detection for green card background works poorly due to similar colors elsewhere
   - **Best approach**: Grayscale threshold <120 → find darkest horizontal rectangle matching button dimensions

3. **Coordinate drift from v14 to run3**
   - v14 found button at (412, 492) — hits left edge ("立即领...")
   - Run3 OpenCV found center at (443, 515) — dead center ("立即...取")
   - Delta: **+31px right, +23px down** — the v14 coordinate was hitting the left third of the button

4. **Why single click fails**
   - The "▼" symbol next to "立即领取" suggests it may be a dropdown-style button
   - First click opens/selects, second click confirms/executes
   - Double-click simulates this two-step interaction

### Window Edge Cases

| Case | GetWindowRect returns | Handling |
|---|---|---|
| Minimized | (-32000,-32000)→(-31840,-31972), size 160×28 | `IsIconic()` → `ShowWindow(SW_RESTORE)` |
| On second monitor | Coordinates outside primary screen range | `SetWindowPos()` to force onto primary monitor |
| Behind other windows | Valid rect but not foreground | `SetForegroundWindow()` + wait 500ms |

### Why Not pywinauto?

```python
# pywinauto UIA sees:
# Chrome Legacy Window  (class name)
# └── No child elements accessible
#
# Electron renders content in Chromium,
# which is opaque to Windows Accessibility API.
# Hence: screenshot + pixel analysis approach.
```

### OpenCV Detection Parameters

```python
# Current working params for button detection:
gray_threshold = 120          # Below = "dark" (button background)
dilate_kernel = (6, 6)       # Connect fragmented dark pixels
min_width, max_width = 55, 115   # Button width range (px)
min_height, max_height = 22, 48  # Button height range (px)
min_area = 1000              # Minimum contour area to consider
search_region = (left+60, top+420, left+180, top+510)  # Green card bottom area
```
