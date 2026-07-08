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

---

## v9 Freeze Fix (2026-07-08)

### Root Cause Analysis — Why Automation Froze WorkBuddy

**Evidence from 2026-07-07 03:55 automated run:**
- `step2_window.png` == `step3_panel.png` == `step6_result.png` (identical 131KB images)
- Panel never opened after avatar click → 0% pixel change
- `step4_btn_preview.png` captured text fragments, not the button → OpenCV misdetection
- Script still returned `"status": "success"` (FALSE POSITIVE)

**6 Root Causes Identified:**

| # | Root Cause | Severity | Fix |
|---|-----------|----------|-----|
| A | **Panel didn't open but script continued blindly** | P0 | Pixel-diff validation; abort if <3% change |
| B | **OpenCV detected wrong target (text fragments)** | P0 | Sanity check: brightness <150, size ratio <70%, min area >400px |
| C | **Always returned "success" regardless of outcome** | P0 | Real status reporting with reason codes |
| D | **5 window-manipulation cycles in 8s bombarded Electron main thread** | P1 | Consolidated to single `activate_window_once()` call |
| E | **Sign-in panel left open after execution (dirty state)** | P1 | `cleanup_panel()` sends Escape key |
| F | **No screen lock check at 4AM** | P2 | `is_screen_locked()` via `OpenInputDesktop` |

### Changes from v8 → v9

```
v8 flow: find → activate×2+position+activate → click → activate → detect → activate+move+doubleclick → grab → [return success]
v9 flow: lock_check → find → activate_once+position → click → [validate pixel diff] → detect+[validate btn] → move+doubleclick → grab+cleanup → [real status]
```

Key behavioral differences:
1. **Aborts on locked screen** instead of sending pyautogui clicks into void
2. **Aborts if panel doesn't open** instead of double-clicking wrong coordinates
3. **Falls back to percentage coords if detection fails validation**
4. **Returns error status** when things go wrong (no more false positives)
5. **Closes panel after signing** to prevent frozen/half-open UI state
6. **Only 1 window activation** instead of 4 (reduces Electron thread stress)

### v9.2 Self-Review Fixes (2026-07-08)

After first v9 implementation, a second-pass review found 4 remaining issues:

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | `AllowSetForegroundWindow(pid)` passed WorkBuddy's PID — wrong; the calling process (automation) needs the right, so `SetForegroundWindow` stayed subject to foreground-lock timeout | P1 | Changed to `AllowSetForegroundWindow(0xFFFFFFFF)` (ASFW_ANY) |
| 2 | No retry when panel failed to open → daily automation would abort every day if WorkBuddy left on non-dashboard view (e.g. NRC) | P1 | Added 1 retry: `press("escape")` to close popover, then click avatar again; re-check pixel diff |
| 3 | `OpenInputDesktop` used `0x20000000` (GENERIC_EXECUTE, wrong value) with misleading comment | P2 | Fixed to `0x80000000` (GENERIC_READ) + correct comment |
| 4 | Dead code `extrema = diff.getextrema()` in `compute_pixel_diff` | P3 | Removed |

**Key finding during review:** The 09:39 v8 "successful" sign-in actually double-clicked a wrong coordinate (panel never opened, NRC view active), silently navigating WorkBuddy to the NRC panel. That mis-navigation is the visible "freeze" symptom. v9.2 reliably blocks it.

**Threshold calibration:** Real panel-open = 6.6% pixel change (per 06-20 log). Abort threshold = 3.0%. NRC-view false change = 2.9%. Gap is clean.
