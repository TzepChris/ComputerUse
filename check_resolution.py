import pyautogui
import mss

print("--- PyAutoGUI (Logical) ---")
width, height = pyautogui.size()
print(f"Size: {width}x{height}")

print("\n--- MSS (Physical) ---")
with mss.mss() as sct:
    for i, monitor in enumerate(sct.monitors):
        print(f"Monitor {i}: {monitor}")
