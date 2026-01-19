"""
Windows App Control - foreground window/process utilities for reliable app focus/launch.
"""
import time
import sys

if sys.platform != 'win32':
    raise ImportError("win_app_control is Windows-only")

import ctypes
import psutil
import win32gui
import win32process
import win32con
import pyautogui

# App name -> process executable mapping (lowercase keys)
APP_PROCESS_MAP = {
    'chrome': 'chrome.exe',
    'google chrome': 'chrome.exe',
    'firefox': 'firefox.exe',
    'edge': 'msedge.exe',
    'microsoft edge': 'msedge.exe',
    'spotify': 'Spotify.exe',
    'notepad': 'notepad.exe',
    'explorer': 'explorer.exe',
    'file explorer': 'explorer.exe',
    'vscode': 'Code.exe',
    'visual studio code': 'Code.exe',
    'code': 'Code.exe',
    'cursor': 'Cursor.exe',
    'discord': 'Discord.exe',
    'slack': 'slack.exe',
    'teams': 'Teams.exe',
    'microsoft teams': 'Teams.exe',
    'word': 'WINWORD.EXE',
    'excel': 'EXCEL.EXE',
    'powerpoint': 'POWERPNT.EXE',
    'outlook': 'OUTLOOK.EXE',
    'terminal': 'WindowsTerminal.exe',
    'windows terminal': 'WindowsTerminal.exe',
    'cmd': 'cmd.exe',
    'powershell': 'powershell.exe',
    'calculator': 'Calculator.exe',
    'calc': 'Calculator.exe',
    'paint': 'mspaint.exe',
    'snipping tool': 'SnippingTool.exe',
    'settings': 'SystemSettings.exe',
}


def get_foreground_window_info():
    """
    Get info about the current foreground window.
    Returns dict with 'hwnd', 'title', 'pid', 'process_name' or None if failed.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        try:
            process = psutil.Process(pid)
            process_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = None
        
        return {
            'hwnd': hwnd,
            'title': title,
            'pid': pid,
            'process_name': process_name
        }
    except Exception:
        return None


def is_app_foreground(app_name):
    """
    Check if the specified app is currently in the foreground.
    app_name can be a friendly name (e.g., 'chrome') or process name (e.g., 'chrome.exe').
    Returns True/False.
    """
    info = get_foreground_window_info()
    if not info or not info.get('process_name'):
        return False
    
    current_process = info['process_name'].lower()
    
    # Check direct process name match
    if app_name.lower() == current_process or app_name.lower() + '.exe' == current_process:
        return True
    
    # Check via mapping
    target_process = APP_PROCESS_MAP.get(app_name.lower(), '').lower()
    if target_process and target_process == current_process:
        return True
    
    return False


def find_window_by_process(process_name):
    """
    Find windows belonging to a process by name.
    Returns list of (hwnd, title) tuples.
    """
    process_name_lower = process_name.lower()
    windows = []
    
    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            if proc.name().lower() == process_name_lower:
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only include windows with titles
                    windows.append((hwnd, title))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return True
    
    win32gui.EnumWindows(enum_callback, None)
    return windows


def focus_window(hwnd):
    """
    Bring a window to the foreground by its handle.
    Returns True if successful.
    """
    try:
        # If minimized, restore it first
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        
        # Try multiple methods to bring to foreground
        # Method 1: SetForegroundWindow (may fail due to Windows restrictions)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        
        # Method 2: Use AttachThreadInput trick for stubborn windows
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
            foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            
            if foreground_thread != target_thread:
                ctypes.windll.user32.AttachThreadInput(foreground_thread, target_thread, True)
                win32gui.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(foreground_thread, target_thread, False)
        except Exception:
            pass
        
        # Brief wait for focus to take effect
        time.sleep(0.1)
        
        # Verify
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def focus_app(app_name):
    """
    Focus an app by its friendly name or process name.
    Returns True if successful, False if app not found or focus failed.
    """
    # Resolve to process name
    process_name = APP_PROCESS_MAP.get(app_name.lower(), app_name)
    if not process_name.lower().endswith('.exe'):
        process_name = process_name + '.exe'
    
    windows = find_window_by_process(process_name)
    if not windows:
        return False
    
    # Try to focus the first window with a title
    for hwnd, title in windows:
        if focus_window(hwnd):
            return True
    
    return False


def wait_for_app_foreground(app_name, timeout=5.0, poll_interval=0.2):
    """
    Wait for an app to become the foreground window.
    Returns True if app is foreground within timeout, False otherwise.
    """
    start = time.time()
    while time.time() - start < timeout:
        if is_app_foreground(app_name):
            return True
        time.sleep(poll_interval)
    return False


def launch_app_via_start_menu(app_name, wait_timeout=5.0):
    """
    Launch an app using Windows Start menu search.
    This is a fallback when the app isn't already running.
    Returns True if app becomes foreground within timeout.
    """
    # Press Win key to open Start menu
    pyautogui.press('win')
    time.sleep(0.3)
    
    # Type the app name
    pyautogui.write(app_name, interval=0.02)
    time.sleep(0.3)
    
    # Press Enter to launch
    pyautogui.press('enter')
    
    # Wait for app to open and become foreground
    return wait_for_app_foreground(app_name, timeout=wait_timeout)


def open_app(app_name, focus_timeout=2.0, launch_timeout=5.0):
    """
    Open an app: focus if already running, otherwise launch via Start menu.
    Returns (success: bool, method: str) where method is 'focused', 'launched', or 'failed'.
    """
    # First try to focus if already running
    if focus_app(app_name):
        if wait_for_app_foreground(app_name, timeout=focus_timeout):
            return True, 'focused'
    
    # Not running or focus failed, try launching
    if launch_app_via_start_menu(app_name, wait_timeout=launch_timeout):
        return True, 'launched'
    
    return False, 'failed'


def assert_foreground(app_name):
    """
    Assert that the specified app is in the foreground.
    Returns True if correct app is foreground, False otherwise.
    Use this to verify after actions that should have focused an app.
    """
    return is_app_foreground(app_name)


# ---------------------------------------------------------------------------
# Window maximize helpers
# ---------------------------------------------------------------------------

# Processes we should never maximize (agent UI, IDE, etc.)
SKIP_MAXIMIZE_PROCESSES = {
    'python.exe',
    'pythonw.exe',
    'cursor.exe',
    'code.exe',
}


def is_window_maximized(hwnd):
    """Return True if the window is maximized."""
    return bool(win32gui.IsZoomed(hwnd))


def maximize_window(hwnd):
    """
    Maximize a window by its handle.
    Returns True if the window is now maximized, False otherwise.
    """
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(0.05)
        return is_window_maximized(hwnd)
    except Exception:
        return False


def maximize_foreground_window():
    """
    Maximize the current foreground window.
    Skips if the window belongs to a process in SKIP_MAXIMIZE_PROCESSES.
    Returns (success: bool, reason: str).
    """
    info = get_foreground_window_info()
    if not info:
        return False, 'no_foreground_window'

    hwnd = info['hwnd']
    process_name = (info.get('process_name') or '').lower()

    # Skip maximizing the agent's own window or IDE
    if process_name in SKIP_MAXIMIZE_PROCESSES:
        return False, 'skip_process'

    if is_window_maximized(hwnd):
        return True, 'already_maximized'

    if maximize_window(hwnd):
        return True, 'maximized'
    return False, 'failed'


def get_screen_size_diagnostic():
    """
    Return diagnostic info about screen sizes from different sources.
    Useful for detecting DPI mismatches.
    """
    import mss
    
    # pyautogui size (affected by DPI awareness)
    pa_width, pa_height = pyautogui.size()
    
    # mss size (physical pixels)
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        mss_width = monitor['width']
        mss_height = monitor['height']
    
    # Windows API size
    user32 = ctypes.windll.user32
    win_width = user32.GetSystemMetrics(0)
    win_height = user32.GetSystemMetrics(1)
    
    return {
        'pyautogui': (pa_width, pa_height),
        'mss': (mss_width, mss_height),
        'win32': (win_width, win_height),
        'mismatch': (pa_width != mss_width) or (pa_height != mss_height)
    }
