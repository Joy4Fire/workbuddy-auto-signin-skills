#!/usr/bin/env python3
"""Enumerate all top-level windows and check which belong to WorkBuddy processes."""
import ctypes
from ctypes import wintypes
import subprocess

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Get all WorkBuddy PIDs
result = subprocess.run(
    ["tasklist", "/FI", "IMAGENAME eq WorkBuddy.exe", "/FO", "CSV", "/NH"],
    capture_output=True, text=True
)
wb_pids = set()
for line in result.stdout.strip().splitlines():
    parts = line.split(",")
    if len(parts) >= 2:
        try:
            wb_pids.add(int(parts[1].strip('"')))
        except ValueError:
            pass

print(f"WorkBuddy PIDs: {sorted(wb_pids)}")
print(f"Total: {len(wb_pids)} processes")
print()

# EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
)
results = []

def enum_cb(hwnd, lparam):
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        visible = user32.IsWindowVisible(hwnd)
        results.append((hwnd, pid.value, buf.value, visible))
    return True

user32.EnumWindows(EnumWindowsProc(enum_cb), 0)

# Find all windows owned by WorkBuddy
print("=== Windows owned by WorkBuddy PIDs ===")
for hwnd, pid, title, visible in results:
    if pid in wb_pids:
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        print(f"  HWND={hwnd}  PID={pid}  Visible={visible}  Title={title!r}")
        print(f"    Rect: ({rect.left},{rect.top}) -> ({rect.right},{rect.bottom})  [{rect.right-rect.left}x{rect.bottom-rect.top}]")

print()
print("=== All windows containing 'WorkBuddy' in title ===")
for hwnd, pid, title, visible in results:
    if "WorkBuddy" in title:
        print(f"  HWND={hwnd}  PID={pid}  Visible={visible}  Title={title!r}")
