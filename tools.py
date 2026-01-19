import sys
import pyautogui
import time
import pyperclip

# Configure pyautogui
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.05 # Reduced pause between actions for speed

# Windows-only window management import
if sys.platform == 'win32':
    from win_app_control import (
        maximize_foreground_window as _maximize_fg,
        open_app as _open_app
    )
else:
    _maximize_fg = None
    _open_app = None

def get_screen_size():
    return pyautogui.size()

def denormalize(x, y):
    width, height = get_screen_size()
    return int(x * width / 1000), int(y * height / 1000)

def click(x, y, normalized=True):
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.click(x, y)

def right_click(x, y, normalized=True):
    """Right click to open context menus"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.rightClick(x, y)

def middle_click(x, y, normalized=True):
    """Middle click (useful for opening links in new tabs, paste in terminals)"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.middleClick(x, y)

def double_click(x, y, normalized=True):
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.doubleClick(x, y)

def triple_click(x, y, normalized=True):
    """Triple click to select entire line/paragraph"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.tripleClick(x, y)

def type_text(text):
    pyautogui.write(text, interval=0.01) # Faster typing

def type_unicode(text):
    """Type text including unicode characters (slower but supports all characters)"""
    import pyperclip
    old_clipboard = pyperclip.paste()
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.05)
    pyperclip.copy(old_clipboard)

def hotkey(*keys):
    pyautogui.hotkey(*keys, interval=0.1)

def clear_field(x, y, normalized=True):
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.click(x, y)
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.press('backspace')
    time.sleep(0.1)

def press_key(key):
    pyautogui.press(key)

def hold_key(key, duration=0.5):
    """Hold a key down for a duration (useful for games or special interactions)"""
    pyautogui.keyDown(key)
    time.sleep(duration)
    pyautogui.keyUp(key)

def scroll(amount):
    # positive for up, negative for down
    pyautogui.scroll(amount)

def scroll_at(x, y, amount, normalized=True):
    """Scroll at a specific location"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.scroll(amount, x=x, y=y)

def horizontal_scroll(amount):
    """Horizontal scroll (positive for right, negative for left)"""
    pyautogui.hscroll(amount)

def drag(x1, y1, x2, y2, normalized=True):
    if normalized:
        x1, y1 = denormalize(x1, y1)
        x2, y2 = denormalize(x2, y2)
    pyautogui.moveTo(x1, y1)
    pyautogui.dragTo(x2, y2, duration=0.2) # Faster drag

def move_mouse(x, y, normalized=True):
    """Move mouse without clicking (for hover effects, tooltips, menus)"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.moveTo(x, y)

def get_mouse_position():
    """Get current mouse position as normalized coordinates"""
    x, y = pyautogui.position()
    width, height = get_screen_size()
    return int(x * 1000 / width), int(y * 1000 / height)

def copy_to_clipboard():
    """Send Ctrl+C and return clipboard contents"""
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.1)
    return pyperclip.paste()

def paste_from_clipboard():
    """Paste from clipboard using Ctrl+V"""
    pyautogui.hotkey('ctrl', 'v')

def set_clipboard(text):
    """Set clipboard contents"""
    pyperclip.copy(text)

def get_clipboard():
    """Get clipboard contents"""
    return pyperclip.paste()

def run_shell_command(command):
    """Run a shell command and return output"""
    import subprocess
    import sys
    try:
        if sys.platform == 'win32':
            # Use PowerShell on Windows for better compatibility with agent's expectations ($HOME, etc.)
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=10
            )
        else:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

def click_and_hold(x, y, duration=1.0, normalized=True):
    """Click and hold at a position (for drag menus, long press actions)"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.mouseDown(x, y)
    time.sleep(duration)
    pyautogui.mouseUp()

def shift_click(x, y, normalized=True):
    """Shift+Click for range selection"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.click(x, y, _keys=['shift'])

def ctrl_click(x, y, normalized=True):
    """Ctrl+Click for multi-selection or opening links in new tabs"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.click(x, y, _keys=['ctrl'])

def alt_click(x, y, normalized=True):
    """Alt+Click for various special interactions"""
    if normalized:
        x, y = denormalize(x, y)
    pyautogui.click(x, y, _keys=['alt'])


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

def maximize_active_window():
    """
    Maximize the currently active (foreground) window.
    Returns (success: bool, reason: str).
    On non-Windows platforms returns (False, 'unsupported').
    """
    if _maximize_fg is None:
        return False, 'unsupported'
    return _maximize_fg()

def open_app(app_name):
    """
    Open an app: focus if already running, otherwise launch.
    Returns (success: bool, method: str).
    """
    if _open_app is None:
        return False, 'unsupported'
    return _open_app(app_name)
