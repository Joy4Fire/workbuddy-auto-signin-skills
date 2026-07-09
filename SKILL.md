---
name: workbuddy-auto-signin
description: >
  Automate daily sign-in for WorkBuddy (腾讯云 CodeBuddy AI 助手) on Windows.
  v10 Vision-Driven Edition: uses the agent's multimodal vision capabilities
  for ALL UI element detection (avatar, sign-in button, result verification).
  No OpenCV. No hardcoded coordinates. The Python script is a thin helper
  for window management, screenshots, and clicks; the agent itself is the
  "vision model" that reads screenshots and determines coordinates.
  Trigger when user says: 签到, 每日签到, WorkBuddy签到, 自动领取积分, sign in, daily check-in.
license: Apache-2.0
version: 10.0.0
tags: [automation, windows, workbuddy, desktop-ui, vision-model, agent-driven]
---

# WorkBuddy Auto Sign-in v10 — Vision-Driven Edition

Automated daily sign-in for **WorkBuddy** using the agent's multimodal vision capabilities.

> ⚠️ **Windows only** — relies on Win32 APIs, `pyautogui`, `PIL`, `numpy`.
> No `opencv-python` required.

---

## When to Use

Invoke this skill when the user requests:
- 签到 / 每日签到 / WorkBuddy签到 / 自动领取积分
- sign in / daily check-in / claim daily rewards

## Architecture

This skill uses an **agent-driven workflow** where the agent's multimodal vision is the "vision model":

```
┌────────────────────────┐         ┌─────────────────────────────────┐
│   Python Helper        │  JSON   │   Agent (multimodal LLM)        │
│   (auto_signin.py)     │ ◀─────▶ │                                 │
│                        │         │  • Reads screenshots            │
│  • Window management   │         │  • Identifies UI elements       │
│  • Screenshot capture  │         │  • Determines coordinates       │
│  • Click execution     │         │  • Verifies results             │
│  • Input testing       │         │  • Makes decisions              │
│  • Keyboard input      │         │                                 │
└────────────────────────┘         └─────────────────────────────────┘
```

**The Python script has ZERO detection logic.** It's a thin CLI wrapper:

| Subcommand | Purpose |
|------------|---------|
| `find-window` | Find WorkBuddy HWND + rect |
| `activate <HWND>` | Activate & position window to primary screen |
| `screenshot --output <path> [--region x1,y1,x2,y2]` | Capture screenshot |
| `click <X> <Y> [single\|double]` | Click at screen coordinates |
| `press-key <KEY>` | Press a keyboard key |
| `check-lock` | Check if screen is locked |
| `wake-screen` | Wake display from sleep + verify input availability |

All "intelligence" comes from the agent reading screenshots and understanding the UI.

---

## Step-by-Step Workflow

**IMPORTANT**: Follow these steps EXACTLY in order. The agent MUST READ each screenshot before deciding what to do next.

### Step 0: Environment Check

```bash
# Check if screen is locked
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" check-lock
```

- If `screen_locked: true` → **ABORT**. Report: "Screen is locked, cannot sign in."
- If `screen_locked: false` → continue.

### Step 0.5: Wake Display & Verify Input (critical for overnight automation)

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" wake-screen
```

This performs two things in one shot:
1. **Wakes the display** by activating the WorkBuddy window (window-rendering change triggers monitor wake)
2. **Verifies input simulation works** by clicking the user avatar at bottom-left and measuring pixel change

The response `status` field tells you what happened:

| `status` | Meaning | Action |
|----------|---------|--------|
| `ok` | Display awake AND input working (avatar click produced >1% change) | ✅ Proceed |
| `input_blocked` | Session isolation — input events can't reach desktop | ❌ **ABORT** — retrying won't help |
| `screenshots_broken` | Screenshots not capturing real content | ❌ **ABORT** — environment issue |
| `window_not_found` | WorkBuddy not running | ❌ **ABORT** — start WorkBuddy first |

**Why click the avatar (not Shift key)?** Shift key has near-zero visual side-effects in most UI states (no popover to close, no focus indicator), so 0% change from Shift doesn't prove input is blocked. Clicking the avatar is definitive — if the panel doesn't open, the click didn't reach the window. The panel is then closed with Escape so it doesn't interfere with the actual sign-in flow.

### Step 1: Find & Activate Window

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" find-window
```

- If error → **ABORT**. Report: "WorkBuddy window not found."
- If ok → note `hwnd` and `rect` values, then activate:

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" activate <HWND>
```

- Note the `rect` from the response (window coordinates).

### Step 2: Capture Baseline Screenshot

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" screenshot --output "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\templates\baseline.png" --region <RECT_AS_X1,Y1,X2,Y2>
```

Use the `rect` from Step 1 as the `--region` parameter (e.g., `512,216,2048,1223`).

Then **READ the screenshot**:
```
Use the Read tool on: C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\templates\baseline.png
```

**Analyze the screenshot** and answer:
- Where is the user avatar/icon in the bottom-left sidebar?
- What are its **screen coordinates** (pixel position on the full screen)?
- Is there any popup/dialog blocking the view (e.g., IDM error dialog)?

Report the avatar coordinates as `(x, y)` in absolute screen pixels.

### Step 3: Click Avatar to Open User Menu

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" click <AVATAR_X> <AVATAR_Y> single
```

Wait 3 seconds, then capture the menu screenshot:

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" screenshot --output "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\templates\panel.png" --region <RECT>
```

**READ the panel screenshot** and analyze:
- Did the user menu open? (Look for "Buddy 加油站" sign-in card)
- If NOT opened (looks same as baseline): Press Escape, wait 1s, retry avatar click once.
- If still NOT opened → **ABORT**. Report: "Menu did not open. WorkBuddy may be on a non-dashboard view."

### Step 4: Find & Click Sign-in Button

Look at the panel screenshot from Step 3. Find the **"立即领取"** (claim now) button inside the green/teal "Buddy 加油站" sign-in card.

**IMPORTANT**: There are TWO button states:
- **"立即领取"** (teal/green) — click to claim today's reward
- **"今日已领"** (grey/disabled) — already claimed today, no action needed

**Analyze the screenshot** and report:
- If button shows **"今日已领"** → Report "Already signed in today" and skip to Step 6.
- If button shows **"立即领取"** → report its center coordinates `(x, y)` and proceed to click.

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" click <BUTTON_X> <BUTTON_Y> double
```

**IMPORTANT**: The sign-in button requires a **double-click**. Single click only focuses the button but does NOT trigger the sign-in action.

### Step 5: Verify Result

Wait 4 seconds for the toast notification, then capture:

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" screenshot --output "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\templates\result.png" --region <RECT>
```

**READ the result screenshot** and verify:
- Is there a "领取成功" / "已领取" toast or indicator?
- Or does the button now show "已领取" (already claimed)?
- Report the final status.

### Step 6: Cleanup

```bash
"C:\Users\18771\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\18771\.workbuddy\skills\workbuddy-auto-signin\scripts\auto_signin.py" press-key escape
```

This closes the sign-in panel so WorkBuddy isn't left in a half-open state.

---

## Handling Edge Cases

The agent's vision capabilities handle these naturally:

| Situation | How to Handle |
|-----------|---------------|
| IDM/error popup overlaying window | Detect in baseline screenshot, dismiss first (click "确定" or close button) |
| WorkBuddy on chat view (not dashboard) | Detect in screenshot, click home/logo icon to navigate back, then retry |
| Sign-in already done ("今日已领") | Detect button text change in Step 4, skip to Step 6, report "already signed in" |
| Button location shifted | Vision model finds it wherever it is — no hardcoded positions |
| Different window size/layout | Vision model adapts — no percentage coordinates |
| Network error in panel | Detect error state, abort cleanly |
| Multi-monitor (Chrome on second screen) | `find-window` correctly returns IDE window, not Chrome client |

## Input Blocking & Display Sleep (Overnight Automation)

When running at night/early morning (e.g., 4AM), two issues can occur:

### 1. Display Sleep
The monitor may have entered power-saving mode. This is handled by **Step 0.5 `wake-screen`** which activates the WorkBuddy window — the window-rendering change reliably wakes the display.

### 2. Session Isolation
If `wake-screen` reports `input_blocked`, this means the automation runs in a non-interactive desktop session where input events can't reach the UI. **Screenshots still work but clicks/keyboard don't register.**

Possible causes:
- Automation process runs in Session 0 or non-interactive desktop
- UIPI (User Interface Privilege Isolation) blocking
- Windows secure desktop active (UAC / lock screen intermediate state)

**When `input_blocked`: ABORT immediately.** Retrying won't help — the session itself prevents input injection. This needs to be resolved at the WorkBuddy automation scheduling level (run as logged-in user, not as service).

## Dependencies

```bash
pip install pyautogui pillow numpy
```

Note: **No opencv-python needed** (unlike v9 and earlier).

## Configuration

Config file: `config/signin_config.json`

Only window positioning settings remain (no detection thresholds):

```json
{
  "window_position": {
    "width_percent": 0.6,
    "height_percent": 0.7,
    "x_percent": 0.2,
    "y_percent": 0.15
  }
}
```

---

## Why Vision Model?

OpenCV thresholds break when UI changes; the agent's multimodal vision understands any layout naturally.

## Why Double-Click?

Single click only focuses the sign-in button, doesn't trigger the action.

## Why No Hardcoded Percentages?

Vision model finds elements wherever they are — adaptive by nature.

## Why Input Test?

4AM automation may run in a session-isolated context; detecting this early prevents wasted retries.

## Why Thin Helper?

Separation of concerns: Python handles mechanics, agent handles intelligence.

---

_This skill is not officially affiliated with WorkBuddy._
