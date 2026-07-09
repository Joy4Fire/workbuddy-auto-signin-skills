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

### Deployment / Remote (2026-07-08)

- Remote switched from HTTPS-with-embedded-PAT to **SSH** (`git@github.com:Joy4Fire/workbuddy-auto-signin-skills.git`).
- Local SSH key: `~/.ssh/id_rsa` (no passphrase, identity `wangjian@223.2.44.120`), registered as an Authentication Key on the GitHub account.
- Push workflow: key must be loaded into ssh-agent first (`ssh-add ~/.ssh/id_rsa`), then `git push origin main` works with no token in the URL.
- Reason for switch: avoid leaking a plaintext PAT in the remote URL.

---

## v10 Architecture — Vision-Driven (2026-07-09)

### Why v10?

v9.2 used OpenCV grayscale thresholding (gray<120) to find the dark "立即领取" button. This worked but had a structural problem: **any UI change requires re-tuning the threshold or pixel percentages**. After several rounds of "WorkBuddy changed the panel layout → manually re-tune the numbers" cycles, it became clear the detection logic was the wrong layer.

**Insight**: WorkBuddy's automation host is itself a **multimodal LLM (Agent)** that can already understand screenshots perfectly. So instead of trying to encode UI understanding in Python+OpenCV, just let the Agent *be* the vision model.

### Architecture Comparison

**v9.2 (OpenCV-driven)**:
```
Python script:
  - Find window
  - Take screenshot
  - OpenCV: gray<120 threshold → find largest dark blob in ROI
  - Verify blob is button-like (width, height sanity-check)
  - Double-click at center
  - Save result screenshot
```

**v10 (Vision-driven)**:
```
Python helper (350 lines, ZERO detection):
  - find-window / activate / screenshot / click / press-key / check-lock / wake-screen
Agent (multimodal LLM):
  - Read screenshot via Read tool
  - Visually locate avatar / button
  - Report pixel coordinates
  - Send click command
  - Verify result via next screenshot
```

### 4AM Failure Analysis (2026-07-09 03:55-04:05)

**Symptom**: All clicks (pyautogui / SendInput / mouse_event / PostMessage / keyboard) produced 0% pixel change.

**Diagnostic walkthrough** (all in the 4AM run):
- Screenshot worked: minimize+restore produced 48% pixel change → `ImageGrab.grab()` reads GDI/DWM frame buffer fine
- Window responsive: WM_NULL SendMessage returned 0 → message queue is alive
- Window visible: WS_VISIBLE set, WS_DISABLED clear, no layered/transparent flags
- No occlusion: `WindowFromPoint` at click position returned the same HWND
- All input methods failed: 0% change from pyautogui.click, SendInput, mouse_event, PostMessage(WM_LBUTTONDOWN), keyboard F5/Ctrl+R/Escape

**Root cause**: Windows desktop session isolation. The automation process could read the screen (GDI read permission) but could not inject input events into the interactive desktop (write permission denied). This is a system-level security boundary, not a skill bug.

**Why it worked on other days**: 6月21日-7月7日的4AM 全部成功。7月9日失败说明当时系统状态异常（可能是 Windows 更新、UAC 弹窗、锁屏转换中间态等偶发情况）。

**Why `wake-screen` is the right fix**: v10 的 `wake-screen` 用"点击头像 → 是否打开面板"作为判据。`Step 0.5` 执行时如果 `input_blocked`，就**立即 abort**，不浪费 7 步流程的 token。这是 v9.2 缺乏的"早失败"机制。

### v10 Improvements Beyond "Just Use Vision"

1. **No more threshold tuning** — UI changes don't break the skill
2. **Smarter error messages** — Agent can describe what it sees in the screenshot ("I see the user menu is already open, so the avatar click did work")
3. **Faster troubleshooting** — Each step produces a screenshot the Agent can reason about, instead of a binary "did the panel open" check
4. **Lower Python maintenance** — 350 lines vs 700+ lines in v9.2
5. **No opencv-python dependency** — saves ~50MB and eliminates version conflicts

### v10 End-to-End Validation (2026-07-09 10:10)

Full workflow executed successfully:
- Step 0 `check-lock` → `screen_locked: false`
- Step 0.5 `wake-screen` → `status: ok, avatar_click_change_pct: 5.74%`
- Step 1 `find-window` → HWND=10958058 (IDE window)
- Step 1.5 `activate` → window positioned at (512, 216, 2048, 1223)
- Step 2 `screenshot` + Agent vision analysis → avatar at (562, 1158)
- Step 3 `click` → 9.80% pixel change (panel opened)
- Step 3b `screenshot` verification → "和光同尘" user menu visible with "Buddy 加油站" card showing "今日已领"
- Step 6 `press-key escape` → panel closed cleanly

**Note**: The "今日已领" status is expected — the user had already signed in earlier that morning (08:59 manual run). The skill correctly detected this state and would skip the click if running step 4.

### Multi-Monitor / Chrome Edge Case

The system sometimes has a second WorkBuddy window: `"Tencent Cloud WorkBuddy - Google Chrome"` (the web client). This window sometimes parks itself at `(2552, -8) → (5128, 1400)` (a position straddling the two monitors in a dual-display setup).

`find-workbuddy-window` correctly prioritizes the **IDE window** (not the Chrome client) because the daily sign-in panel only exists in the IDE. The Chrome client's "成长计划" / "每日成长答题" features are different functionality, not the daily sign-in reward.

### SSH Deployment Notes (carried over from v9.2)

- Remote: `git@github.com:Joy4Fire/workbuddy-auto-signin-skills.git`
- SSH key: `~/.ssh/id_rsa` (no passphrase)
- Push requires `ssh-add ~/.ssh/id_rsa` first to load the key into the agent
