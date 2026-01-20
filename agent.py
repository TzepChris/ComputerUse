import os
import time
import mss
import mss.tools
from PIL import Image, ImageDraw
import google.generativeai as genai
from openai import OpenAI
import base64
import io
from tools import (
    click, double_click, triple_click, right_click, middle_click,
    type_text, type_unicode, press_key, hold_key, scroll, scroll_at, horizontal_scroll,
    drag, move_mouse, get_screen_size, hotkey, clear_field,
    copy_to_clipboard, paste_from_clipboard, set_clipboard, get_clipboard,
    click_and_hold, shift_click, ctrl_click, alt_click,
    maximize_active_window, open_app, run_shell_command
)
from ui_inspector import get_ui_tree_summary, get_foreground_window_rect
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini - Moved to class init
# genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """
You are a Computer Use Agent. You have control over the user's computer screen and input devices.
Your goal is to help the user with their tasks by seeing the screen and performing actions.

Available actions:

MOUSE ACTIONS:
- CLICK(x, y): Left click at normalized coordinates (x, y) relative to the ATTACHED SCREENSHOT.
- DOUBLE_CLICK(x, y): Double click at normalized coordinates (x, y) relative to the ATTACHED SCREENSHOT.
- TRIPLE_CLICK(x, y): Triple click to select an entire line or paragraph relative to the ATTACHED SCREENSHOT.
- RIGHT_CLICK(x, y): Right click to open context menus relative to the ATTACHED SCREENSHOT.
- MIDDLE_CLICK(x, y): Middle click relative to the ATTACHED SCREENSHOT.
- MOVE_MOUSE(x, y): Move mouse without clicking relative to the ATTACHED SCREENSHOT.
- CLICK_AND_HOLD(x, y, duration): Click and hold at (x, y) relative to the ATTACHED SCREENSHOT.
- SHIFT_CLICK(x, y): Shift+Click at (x, y) relative to the ATTACHED SCREENSHOT.
- CTRL_CLICK(x, y): Ctrl+Click at (x, y) relative to the ATTACHED SCREENSHOT.
- ALT_CLICK(x, y): Alt+Click at (x, y) relative to the ATTACHED SCREENSHOT.
- DRAG(x1, y1, x2, y2): Drag from (x1, y1) to (x2, y2) relative to the ATTACHED SCREENSHOT.

FULL-SCREEN COORDINATE OVERRIDES (use ONLY when you need to click outside the attached screenshot):
- CLICK_SCREEN(x, y)
- DOUBLE_CLICK_SCREEN(x, y)
- TRIPLE_CLICK_SCREEN(x, y)
- RIGHT_CLICK_SCREEN(x, y)
- MIDDLE_CLICK_SCREEN(x, y)
- MOVE_MOUSE_SCREEN(x, y)
- CLICK_AND_HOLD_SCREEN(x, y, duration)
- SHIFT_CLICK_SCREEN(x, y)
- CTRL_CLICK_SCREEN(x, y)
- ALT_CLICK_SCREEN(x, y)
- DRAG_SCREEN(x1, y1, x2, y2)
- SCROLL_AT_SCREEN(x, y, amount)
- CLEAR_FIELD_SCREEN(x, y)

SCROLL ACTIONS:
- SCROLL(amount): Scroll the mouse wheel at current position. Positive for up, negative for down. Use values like 3, 5, -3, -5.
- SCROLL_AT(x, y, amount): Scroll at a specific location.
- HORIZONTAL_SCROLL(amount): Scroll horizontally. Positive for right, negative for left.

KEYBOARD ACTIONS:
- TYPE(text): Type the specified text (ASCII characters only).
- TYPE_UNICODE(text): Type text including special/unicode characters (use for non-English text, emojis).
- PRESS(key): Press a specific key (e.g., 'enter', 'esc', 'backspace', 'tab', 'space', 'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown', 'f1'-'f12', 'win', 'delete').
- HOTKEY(key1, key2, ...): Press a combination of keys (e.g., HOTKEY('ctrl', 'a'), HOTKEY('alt', 'f4'), HOTKEY('ctrl', 'shift', 'esc')).
- HOLD_KEY(key, duration): Hold a key for a duration in seconds.

TEXT FIELD ACTIONS:
- CLEAR_FIELD(x, y): Focus a field at (x, y) and delete all its current text.

CLIPBOARD ACTIONS:
- COPY(): Send Ctrl+C to copy selected content.
- PASTE(): Send Ctrl+V to paste clipboard content.
- SET_CLIPBOARD(text): Set clipboard to specific text (useful before pasting).

WINDOW ACTIONS:
- OPEN_APP(app_name): Open an application by name (e.g., 'notepad', 'chrome', 'calculator'). This is more reliable than searching the Start menu manually.
- MAXIMIZE_WINDOW(): Maximize the currently active window. Use immediately after opening/focusing an app to avoid small-window scrolling problems.

SYSTEM ACTIONS:
- SHELL(command): Execute a shell command (PowerShell). Use this for RELIABLE file operations (e.g., `mkdir`, `copy`, `move`, `del`), opening specific folders, or checking system state. This is much faster and more reliable than GUI clicks for these tasks.
- WAIT(seconds): Wait briefly for UI to load. Use SHORT waits: 0.3-0.5 seconds MAX. The system already handles delays.
- DONE: Signal that the task is finished.

IMPORTANT GUIDELINES:
1. **BE RELIABLE**: For file operations (creating folders, moving files), PREFER using SHELL('mkdir foldername') or similar. GUI context menus can be brittle.
2. **VERIFY SUCCESS**: Do NOT call ACTION: DONE in the same turn as a critical action (like creating a file or opening an app). Perform the action, wait for the next turn to see the result/screen, and ONLY then call DONE if you see it succeeded.
3. **AVOID LOOPS**: If you try the same click/selection twice and the UI does not change, STOP repeating it. Change strategy: close menus with PRESS('esc'), use keyboard navigation (TAB/arrow keys/ENTER), click a different part of the control, or refocus with HOTKEY('ctrl','l') / HOTKEY('ctrl','k') and navigate directly.
3. Be FAST and EFFICIENT. Avoid unnecessary WAIT actions.
3. When typing into a field that may have text, use CLEAR_FIELD(x, y) first.
4. After typing a search query, PRESS('enter') to trigger the search.
5. Use SCROLL(-5) to scroll DOWN and SCROLL(5) to scroll UP.
6. Use MOVE_MOUSE(x, y) to hover over menus before clicking.
7. Use RIGHT_CLICK(x, y) to access context menus.
8. **MAXIMIZE IMMEDIATELY**: After opening or focusing an app (Settings, browser, etc.), call MAXIMIZE_WINDOW() FIRST before interacting with its content.
9. **EFFICIENT SCROLLING**: If you need to scroll through content, prefer PRESS('pagedown') or PRESS('pageup') over repeated small SCROLL actions.
10. **GREEK/UNICODE SUPPORT**: If you need to type Greek or other non-ASCII characters, ALWAYS use TYPE_UNICODE(text).

WINDOW MANAGEMENT TIPS:
1. **ALWAYS MAXIMIZE FIRST**: When you open or switch to an app, call MAXIMIZE_WINDOW() immediately.
2. Use OPEN_APP('appname') instead of manually searching if possible.
3. If a window obstructs your view, MOVE it using DRAG on the title bar.
4. If the screen is cluttered, use HOTKEY('win', 'd') to show desktop.
4. Use HOTKEY('alt', 'tab') to switch focus if the app is open but behind others.
5. To view two things at once, SNAP windows using HOTKEY('win', 'left') or HOTKEY('win', 'right').

WINDOWS SHORTCUTS (use these instead of searching):
- Open Settings: HOTKEY('win', 'i')
- Open Run dialog: HOTKEY('win', 'r')
- See Windows version: HOTKEY('win', 'r') then TYPE('winver') then PRESS('enter')
- Open Task Manager: HOTKEY('ctrl', 'shift', 'esc')
- Open File Explorer: HOTKEY('win', 'e')
- Show Desktop: HOTKEY('win', 'd')
- Lock screen: HOTKEY('win', 'l')
- Screenshot: HOTKEY('win', 'shift', 's')
- Close window: HOTKEY('alt', 'f4')
- Switch windows: HOTKEY('alt', 'tab')

Coordinates: Use normalized coordinates from 0 to 1000 relative to the ATTACHED SCREENSHOT.
(0, 0) is top-left of the screenshot; (1000, 1000) is bottom-right of the screenshot.
The screenshot has a red 10x10 grid overlay to help you align clicks.
- Center of grid cells: 50, 150, 250... 950.
- Grid lines are at 100, 200... 900.
ALWAYS aim for the CENTER of the icon, not the edge.
If you are unsure, you can verify by checking the surrounding grid lines.

UI METADATA:
You will receive a list of "Detected UI Elements" which includes names, types, and coordinates.
If the screenshot is CROPPED to the foreground window (we will explicitly note this), then window=(x,y) matches the screenshot coords: prefer CLICK(x,y).
If the screenshot is NOT cropped (full screen), use screen=(x,y) with CLICK(x,y) (since the screenshot is the full screen).
Only use *_SCREEN actions if you must click outside the attached screenshot region.
The metadata is especially useful when the screen text is blurry or for identifying icon-only buttons.

Format your response CONCISELY:
ACTION: [Action1]
ACTION: [Action2]
...
REASONING: [Optional, one sentence max]

Output multiple ACTIONs when they can be performed in sequence without seeing the screen.
Do NOT use WAIT unless the UI truly needs time to load (e.g., after opening an app).
"""

# Maximum context messages to keep (system prompt + recent exchanges)
MAX_CONTEXT_MESSAGES = 5

# Performance features (tunable)
CROP_TO_FOREGROUND_WINDOW = True  # smaller screenshot region => faster VLM
ENABLE_FAST_PATH = True           # run deterministic steps without calling the LLM
ENABLE_TEXT_ONLY_FIRST = False    # optional: try a text-only call before sending an image
GEMINI_STREAM_ACTIONS = False     # experimental: execute actions while streaming output

# Upload-size cap for screenshots (smaller => faster upload/processing)
MAX_IMAGE_WIDTH = 768  # reduced from 1024 for speed

def _ahash(image: Image.Image, hash_size: int = 8) -> int:
    """
    Average-hash for quick "did the screen change?" detection.
    Returns a hash_size*hash_size bit integer.
    """
    img = image.convert("L").resize((hash_size, hash_size), Image.Resampling.BILINEAR)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for i, p in enumerate(pixels):
        if p >= avg:
            bits |= (1 << i)
    return bits

def _hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()

class ComputerUseAgent:
    def __init__(self, api_keys=None, model_name='gemini-3-flash-preview'):
        self.api_keys = api_keys or {}
        self.model_name = model_name
        self.usage_file = "api_usage.json"
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.load_usage()
        
        if 'gemini' in self.api_keys:
            genai.configure(api_key=self.api_keys['gemini'])
        
        self.xai_client = None
        if 'xai' in self.api_keys and self.api_keys['xai']:
            self.xai_client = OpenAI(
                api_key=self.api_keys['xai'],
                base_url="https://api.x.ai/v1",
            )
            
        self.model = None
        self.update_model(self.model_name)
        
        self.width, self.height = get_screen_size()
        self.should_stop = False
        # Capture context for mapping screenshot-relative coords back to screen coords.
        self._capture_context = None

    def _is_non_ascii(self, s: str) -> bool:
        return any(ord(ch) > 127 for ch in s)

    def _extract_url(self, text: str):
        import re
        m = re.search(r"(https?://\\S+)", text or "", re.IGNORECASE)
        if not m:
            return None
        return m.group(1).rstrip(").,;\\\"'")

    def _extract_spotify_query(self, text: str):
        import re
        t = (text or "").strip()
        m = re.search(r"search\\s+(?:song\\s*)?[:\\-]?\\s*(.+?)(?:\\s+and\\s+|$)", t, re.IGNORECASE)
        if not m:
            return None
        q = m.group(1).strip().strip("'\\\"")
        if len(q) < 2:
            return None
        return q

    def _fast_path_actions(self, user_instruction: str):
        """
        Return a list of ACTION lines to execute before calling the LLM, or None.
        These are safe, deterministic steps that commonly precede interactive work.
        """
        if not ENABLE_FAST_PATH:
            return None

        instruction = user_instruction or ""
        t = instruction.lower()

        url = self._extract_url(instruction)
        if url:
            return [
                "ACTION: OPEN_APP('chrome')",
                "ACTION: MAXIMIZE_WINDOW()",
                "ACTION: HOTKEY('ctrl','l')",
                f"ACTION: TYPE('{url}')",
                "ACTION: PRESS('enter')",
            ]

        if "spotify" in t:
            actions = [
                "ACTION: OPEN_APP('spotify')",
                "ACTION: MAXIMIZE_WINDOW()",
            ]

            # Toggle play/pause via Space in Spotify desktop
            if any(k in t for k in ("pause", "resume", "play")) and "search" not in t:
                actions.append("ACTION: PRESS('space')")
                return actions

            query = self._extract_spotify_query(instruction)
            if query:
                actions.append("ACTION: HOTKEY('ctrl','l')")
                if self._is_non_ascii(query):
                    actions.append(f"ACTION: TYPE_UNICODE('{query}')")
                else:
                    actions.append(f"ACTION: TYPE('{query}')")
                actions.append("ACTION: PRESS('enter')")
                return actions

        return None

    def _response_has_actions(self, response_text: str) -> bool:
        if not response_text:
            return False
        for line in response_text.splitlines():
            if line.strip().upper().startswith("ACTION:"):
                return True
        return False

    def load_usage(self):
        import json
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    self.total_input_tokens = data.get("total_input_tokens", 0)
                    self.total_output_tokens = data.get("total_output_tokens", 0)
                    self.total_cost = data.get("total_cost", 0.0)
            except Exception as e:
                print(f"Error loading usage file: {e}")

    def save_usage(self):
        import json
        try:
            with open(self.usage_file, 'w') as f:
                json.dump({
                    "total_input_tokens": self.total_input_tokens,
                    "total_output_tokens": self.total_output_tokens,
                    "total_cost": self.total_cost
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving usage file: {e}")

    def stop(self):
        self.should_stop = True

    def update_api_keys(self, api_keys):
        self.api_keys = api_keys
        if 'gemini' in self.api_keys:
            genai.configure(api_key=self.api_keys['gemini'])
        
        if 'xai' in self.api_keys and self.api_keys['xai']:
            self.xai_client = OpenAI(
                api_key=self.api_keys['xai'],
                base_url="https://api.x.ai/v1",
            )
        self.update_model(self.model_name)

    def update_model(self, model_name):
        self.model_name = model_name
        if not model_name.startswith('grok'):
            self.model = genai.GenerativeModel(
                self.model_name,
                generation_config={"temperature": 0.0}
            )
        # For Grok, we use the xai_client directly in generate_content

    def capture_screen(self, sct, crop_rect=None):
        """
        Capture either the full primary monitor, or (optionally) a cropped region.
        Returns (PIL.Image, capture_context dict).

        crop_rect is expected as a dict like:
          {left, top, width, height}
        typically from UIAutomation's BoundingRectangle (desktop coordinates).
        """
        monitor = sct.monitors[1]
        region = monitor

        # Default capture context assumes full monitor
        image_left = int(monitor.get("left", 0))
        image_top = int(monitor.get("top", 0))
        image_width = int(monitor["width"])
        image_height = int(monitor["height"])

        # Optionally crop to the foreground window for speed
        if crop_rect and CROP_TO_FOREGROUND_WINDOW:
            try:
                cl = int(crop_rect.get("left", 0))
                ct = int(crop_rect.get("top", 0))
                cw = int(crop_rect.get("width", 0))
                ch = int(crop_rect.get("height", 0))

                if cw > 50 and ch > 50:
                    ml = int(monitor.get("left", 0))
                    mt = int(monitor.get("top", 0))
                    mr = ml + int(monitor["width"])
                    mb = mt + int(monitor["height"])

                    left = max(ml, min(mr - 1, cl))
                    top = max(mt, min(mb - 1, ct))
                    right = max(left + 1, min(mr, cl + cw))
                    bottom = max(top + 1, min(mb, ct + ch))
                    width = right - left
                    height = bottom - top

                    if width > 50 and height > 50:
                        region = {"left": left, "top": top, "width": width, "height": height}
                        image_left, image_top, image_width, image_height = left, top, width, height
            except Exception:
                region = monitor

        screenshot = sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Draw a semi-transparent grid overlay to help localization
        draw = ImageDraw.Draw(img, "RGBA")
        width, height = img.size
        step_x = max(1, width // 10)
        step_y = max(1, height // 10)
        for i in range(1, 10):
            x = i * step_x
            draw.line([(x, 0), (x, height)], fill=(255, 0, 0, 128), width=2)
        for i in range(1, 10):
            y = i * step_y
            draw.line([(0, y), (width, y)], fill=(255, 0, 0, 128), width=2)

        # Resize image to speed up upload and processing
        if img.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / img.width
            img = img.resize((MAX_IMAGE_WIDTH, int(img.height * ratio)), Image.Resampling.BILINEAR)

        capture_context = {
            "image_left": image_left,
            "image_top": image_top,
            "image_width": image_width,
            "image_height": image_height,
            "monitor_left": int(monitor.get("left", 0)),
            "monitor_top": int(monitor.get("top", 0)),
            "physical_screen_width": int(monitor["width"]),
            "physical_screen_height": int(monitor["height"]),
            "logical_screen_width": int(self.width),
            "logical_screen_height": int(self.height),
        }

        return img, capture_context

    def _image_norm_to_screen_norm(self, x_norm: int, y_norm: int):
        """
        Map screenshot-relative (x,y) normalized coords to full-screen normalized coords.
        If capture context is missing, returns the input unchanged.
        """
        ctx = self._capture_context
        if not ctx:
            return int(x_norm), int(y_norm)

        xi = float(x_norm) / 1000.0
        yi = float(y_norm) / 1000.0
        x_phys = ctx["image_left"] + xi * ctx["image_width"]
        y_phys = ctx["image_top"] + yi * ctx["image_height"]

        # physical -> logical
        sx = ctx["logical_screen_width"] / max(1, ctx["physical_screen_width"])
        sy = ctx["logical_screen_height"] / max(1, ctx["physical_screen_height"])
        x_log = (x_phys - ctx["monitor_left"]) * sx
        y_log = (y_phys - ctx["monitor_top"]) * sy

        xn = int(max(0, min(1000, (x_log / max(1, ctx["logical_screen_width"])) * 1000)))
        yn = int(max(0, min(1000, (y_log / max(1, ctx["logical_screen_height"])) * 1000)))
        return xn, yn

    def _track_usage(self, response, log_func):
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count
            output_tokens = usage.candidates_token_count
            
            # Gemini 3 Pricing from screen: $0.50/1M input, $3.00/1M output
            current_cost = (input_tokens / 1_000_000) * 0.50 + (output_tokens / 1_000_000) * 3.00
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += current_cost
            self.save_usage()
            
            log_func(f"  [Usage] Input: {input_tokens}, Output: {output_tokens}, Cost: ${current_cost:.5f}")
            log_func(f"  [Total Usage] Input: {self.total_input_tokens}, Output: {self.total_output_tokens}, Total Cost: ${self.total_cost:.5f}")

    def run_task(self, user_instruction, logger=None):
        def log(msg):
            if logger:
                logger(msg)
            else:
                print(msg)

        log(f"Starting task: {user_instruction}")
        self.should_stop = False # Reset stop flag
        
        messages = [
            {"role": "user", "parts": [SYSTEM_PROMPT]},
        ]
        
        # Track recent scroll actions to detect stuck loops
        recent_scroll_count = 0
        SCROLL_LOOP_THRESHOLD = 3  # Inject hint after this many consecutive scroll-heavy iterations

        # Track repeated action plans / no-progress loops (e.g., clicking same dropdown forever)
        last_action_signature = None
        repeated_action_signature_count = 0
        consecutive_no_action_count = 0
        prev_screen_hash = None
        prev_actions_executed = 0
        unchanged_after_actions_count = 0
        STUCK_REPEAT_THRESHOLD = 3
        STUCK_UNCHANGED_THRESHOLD = 3
        UNCHANGED_HASH_DISTANCE_THRESHOLD = 3  # lower = stricter; 0 means identical hash
        stuck_hint_cooldown = 0
        STUCK_HINT_COOLDOWN_TURNS = 3
        fast_path_attempted = False
        
        with mss.mss() as sct:
            while not self.should_stop:
                start_time = time.perf_counter()

                # Fast-path: do deterministic setup once (no LLM call)
                if not fast_path_attempted:
                    fast_path_attempted = True
                    fast_actions = self._fast_path_actions(user_instruction)
                    if fast_actions:
                        log("Running fast-path actions (no LLM)...")
                        actions_executed = 0
                        for line in fast_actions:
                            if self.should_stop:
                                log("Stop requested. Breaking fast-path actions.")
                                break
                            log(f"  > {line}")
                            self.execute_action(line)
                            actions_executed += 1
                            time.sleep(0.05)
                        if actions_executed > 0:
                            prev_actions_executed = actions_executed
                        time.sleep(0.1)
                        continue

                # Decide whether to crop screenshot to foreground window
                crop_rect = None
                if CROP_TO_FOREGROUND_WINDOW:
                    crop_rect = get_foreground_window_rect()

                log("Capturing screen...")
                capture_start = time.perf_counter()
                img, capture_context = self.capture_screen(sct, crop_rect=crop_rect)
                self._capture_context = capture_context
                capture_end = time.perf_counter()
                log(f"  [Time] Screen capture: {capture_end - capture_start:.3f}s")

                log("Extracting UI metadata...")
                ui_metadata_start = time.perf_counter()
                ui_metadata = get_ui_tree_summary()
                ui_metadata_end = time.perf_counter()
                log(f"  [Time] UI Metadata: {ui_metadata_end - ui_metadata_start:.3f}s")

                # Check whether previous turn's actions actually changed the screen
                try:
                    current_hash = _ahash(img)
                except Exception:
                    current_hash = None
                if current_hash is not None and prev_screen_hash is not None and prev_actions_executed > 0:
                    dist = _hamming_distance(prev_screen_hash, current_hash)
                    if dist <= UNCHANGED_HASH_DISTANCE_THRESHOLD:
                        unchanged_after_actions_count += 1
                    else:
                        unchanged_after_actions_count = 0
                else:
                    unchanged_after_actions_count = 0
                prev_screen_hash = current_hash
                if stuck_hint_cooldown > 0:
                    stuck_hint_cooldown -= 1
                
                is_cropped = (
                    capture_context
                    and (capture_context["image_width"] < capture_context["physical_screen_width"]
                         or capture_context["image_height"] < capture_context["physical_screen_height"])
                )
                crop_note = ""
                if is_cropped:
                    crop_note = (
                        "\n\nNOTE: The attached screenshot is CROPPED to the foreground window. "
                        "Use CLICK(x,y) with screenshot/window-relative coords (prefer UI metadata window=(x,y)). "
                        "Only use *_SCREEN actions if you must click outside the screenshot."
                    )

                user_message = {
                    "role": "user", 
                    "parts": [
                        f"Task: {user_instruction}{crop_note}\n\n{ui_metadata}\n\nCurrent screen state is attached. What are the next actions?",
                        img
                    ]
                }
                messages.append(user_message)
                
                # Prune context to keep it fast - keep system prompt + last few exchanges
                if len(messages) > MAX_CONTEXT_MESSAGES:
                    # Keep system prompt (first message) and last N-1 messages
                    messages = [messages[0]] + messages[-(MAX_CONTEXT_MESSAGES - 1):]
                    log(f"  [Context] Pruned to {len(messages)} messages for speed")
                else:
                    log(f"  [Context] {len(messages)} messages")
                
                try:
                    log(f"Sending to {self.model_name}...")
                    api_start = time.perf_counter()
                    
                    if self.model_name.startswith('grok'):
                        # Prepare messages for Grok (OpenAI format)
                        grok_messages = []
                        for msg in messages:
                            role = "assistant" if msg["role"] == "model" else msg["role"]
                            content = []
                            for part in msg["parts"]:
                                if isinstance(part, str):
                                    content.append({"type": "text", "text": part})
                                elif isinstance(part, Image.Image):
                                    # Convert PIL Image to base64
                                    buffered = io.BytesIO()
                                    part.save(buffered, format="JPEG")
                                    img_str = base64.b64encode(buffered.getvalue()).decode()
                                    content.append({
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{img_str}",
                                            "detail": "high"
                                        }
                                    })
                            grok_messages.append({"role": role, "content": content})
                        
                        response = self.xai_client.chat.completions.create(
                            model=self.model_name,
                            messages=grok_messages,
                            temperature=0.0
                        )
                        response_text = response.choices[0].message.content
                    else:
                        # Gemini flow
                        try:
                            response = None
                            response_text = ""

                            # Optional speed path: try text-only first (no screenshot).
                            if ENABLE_TEXT_ONLY_FIRST:
                                try:
                                    log("  [Speed] Trying text-only call first...")
                                    text_only_messages = list(messages)
                                    # Remove the image from the most recent user message
                                    last = dict(text_only_messages[-1])
                                    if isinstance(last.get("parts"), list) and last["parts"]:
                                        last_text = str(last["parts"][0])
                                        last["parts"] = [last_text + "\n\n(No screenshot attached for this attempt. If UI metadata is sufficient, output ACTIONs now.)"]
                                        text_only_messages[-1] = last
                                    response = self.model.generate_content(
                                        text_only_messages,
                                        request_options={"timeout": 60}
                                    )
                                    self._track_usage(response, log)
                                    response_text = getattr(response, "text", "") or ""
                                except Exception:
                                    response = None
                                    response_text = ""

                            # If text-only didn't produce actions, fall back to vision call.
                            if not response or not self._response_has_actions(response_text):
                                # Use timeout to prevent hanging on slow API calls
                                response = self.model.generate_content(
                                    messages,
                                    request_options={"timeout": 60}
                                )
                                self._track_usage(response, log)
                                response_text = response.text
                        except Exception as e:
                            error_str = str(e).lower()
                            if "404" in str(e) and self.model_name == 'gemini-3-flash-preview':
                                log("Gemini 3 Flash not found, falling back to Gemini 2.0 Flash...")
                                self.model_name = 'gemini-2.0-flash'
                                self.model = genai.GenerativeModel(self.model_name, generation_config={"temperature": 0.0})
                                response = self.model.generate_content(messages, request_options={"timeout": 60})
                                self._track_usage(response, log)
                                response_text = response.text
                            elif "timeout" in error_str or "deadline" in error_str:
                                log("API timeout - retrying with minimal context...")
                                # Retry with only system prompt and current screenshot
                                minimal_messages = [messages[0], messages[-1]]
                                response = self.model.generate_content(minimal_messages, request_options={"timeout": 60})
                                self._track_usage(response, log)
                                response_text = response.text
                            else:
                                raise e
                        # response_text set above
                    
                    api_end = time.perf_counter()
                    log(f"  [Time] API: {api_end - api_start:.3f}s")
                    
                    log(f"Agent Response:\n{response_text}")
                    
                    messages.append({"role": "model", "parts": [response_text]})
                    
                    # Execute all actions found in the response
                    actions_executed = 0
                    execution_start = time.perf_counter()
                    action_results = []
                    is_done = False

                    # Build an "action signature" to detect repeated plans
                    action_lines = []
                    for line in response_text.splitlines():
                        line_upper = line.strip().upper()
                        if line_upper.startswith("ACTION:") and "DONE" not in line_upper:
                            action_lines.append(line.strip())
                    action_signature = "\n".join(action_lines).strip() if action_lines else ""

                    if not action_signature:
                        consecutive_no_action_count += 1
                        repeated_action_signature_count = 0
                        last_action_signature = None
                    else:
                        consecutive_no_action_count = 0
                        if last_action_signature == action_signature:
                            repeated_action_signature_count += 1
                        else:
                            repeated_action_signature_count = 0
                        last_action_signature = action_signature

                    # If we're clearly stuck, inject a hint and (optionally) skip repeating the same actions
                    stuck_repeat = repeated_action_signature_count >= STUCK_REPEAT_THRESHOLD
                    stuck_unchanged = unchanged_after_actions_count >= STUCK_UNCHANGED_THRESHOLD
                    stuck_no_actions = consecutive_no_action_count >= 2
                    should_inject_stuck_hint = (stuck_repeat or stuck_unchanged or stuck_no_actions) and stuck_hint_cooldown == 0

                    if should_inject_stuck_hint:
                        hint = (
                            "SYSTEM HINT: You appear stuck (repeating the same action plan / no visible UI change). "
                            "Stop repeating identical clicks. Change strategy: try ESC to close menus, "
                            "use keyboard navigation (TAB/SHIFT+TAB, arrow keys, ENTER), click a different area, "
                            "or reset focus (e.g., Ctrl+L to address bar) and navigate directly. "
                            "For complex widgets (like Google Flights), prefer going directly to the site/app view "
                            "and then reading the prices from the page before calling DONE."
                        )
                        messages.append({"role": "user", "parts": [hint]})
                        log("  [Hint] Injected stuck-loop correction hint")
                        stuck_hint_cooldown = STUCK_HINT_COOLDOWN_TURNS

                    # If we're repeating the same plan AND the screen isn't changing, don't keep executing it.
                    skip_actions_this_turn = stuck_repeat and stuck_unchanged
                    
                    for line in response_text.splitlines():
                        if self.should_stop:
                            log("Stop requested. Breaking action loop.")
                            break
                        
                        line_upper = line.strip().upper()
                        if line_upper.startswith("ACTION:"):
                            # Check for DONE signal
                            if "DONE" in line_upper:
                                log("Task completed signal received.")
                                is_done = True
                                continue
                            if skip_actions_this_turn:
                                continue
                                
                            log(f"  > {line.strip()}")
                            result = self.execute_action(line)
                            if result:
                                action_results.append(result)
                            actions_executed += 1
                            time.sleep(0.05)  # Minimal delay between actions
                    
                    execution_end = time.perf_counter()
                    
                    if actions_executed > 0:
                        log(f"  [Time] Executed {actions_executed} actions in {execution_end - execution_start:.3f}s")
                    
                    if action_results:
                        results_text = "Action results:\n" + "\n".join(action_results)
                        messages.append({"role": "user", "parts": [results_text]})
                        log("  [Context] Added action results to message history")
                    
                    if is_done:
                        break
                    
                    # Detect scroll-loop: count scroll actions in this response
                    scroll_actions_this_turn = sum(
                        1 for line in response_text.splitlines()
                        if 'SCROLL' in line.upper() and line.strip().upper().startswith('ACTION:')
                    )
                    if scroll_actions_this_turn >= 1:
                        recent_scroll_count += 1
                    else:
                        recent_scroll_count = 0  # Reset if no scroll this turn
                    
                    # Inject corrective hint if stuck in scroll loop
                    if recent_scroll_count >= SCROLL_LOOP_THRESHOLD:
                        hint = (
                            "SYSTEM HINT: You appear stuck in a scrolling loop. "
                            "Try MAXIMIZE_WINDOW() first to see more content, or use PRESS('pagedown') / PRESS('end') "
                            "instead of repeated small scrolls. Consider if you already have the answer visible."
                        )
                        messages.append({"role": "user", "parts": [hint]})
                        log(f"  [Hint] Injected scroll-loop correction hint")
                        recent_scroll_count = 0  # Reset after injecting hint
                    
                    # Minimal delay before next loop
                    if actions_executed == 0:
                        log("No actions found in response.")
                        time.sleep(0.2)
                    else:
                        time.sleep(0.1)  # Small delay for UI to settle
                    prev_actions_executed = actions_executed
                    
                    loop_end = time.perf_counter()
                    log(f"  [Time] Total loop: {loop_end - start_time:.3f}s")
                    
                except Exception as e:
                    log(f"Error during agent execution: {e}")
                    break

    def execute_action(self, action_line):
        """Executes an action and returns a result string if any (e.g., shell output)"""
        # Improved parser for the action string
        import re
        
        match = re.search(r"ACTION:\s*(\w+)\((.*)\)", action_line, re.IGNORECASE)
        if not match:
            print("Could not parse action from response.")
            return None

        action_name = match.group(1).upper()
        params_str = match.group(2)
        # Parse parameters, handling potential quotes
        params = []
        for p in re.split(r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', params_str):
            p = p.strip().strip("'").strip('"')
            params.append(p)

        # Coordinate mode:
        # - default actions use screenshot-relative coords (mapped via capture context)
        # - *_SCREEN actions use full-screen coords directly (no mapping)
        coord_mode = "image"
        if action_name.endswith("_SCREEN"):
            coord_mode = "screen"
            action_name = action_name[:-7]  # strip "_SCREEN"

        def _xy(i: int = 0, j: int = 1):
            x = int(float(params[i]))
            y = int(float(params[j]))
            if coord_mode == "screen":
                return x, y
            return self._image_norm_to_screen_norm(x, y)

        action_result = None
        try:
            start_time = time.perf_counter()
            if action_name == "CLICK":
                x, y = _xy(0, 1)
                click(x, y)
            elif action_name == "DOUBLE_CLICK":
                x, y = _xy(0, 1)
                double_click(x, y)
            elif action_name == "TRIPLE_CLICK":
                x, y = _xy(0, 1)
                triple_click(x, y)
            elif action_name == "RIGHT_CLICK":
                x, y = _xy(0, 1)
                right_click(x, y)
            elif action_name == "MIDDLE_CLICK":
                x, y = _xy(0, 1)
                middle_click(x, y)
            elif action_name == "MOVE_MOUSE":
                x, y = _xy(0, 1)
                move_mouse(x, y)
            elif action_name == "CLICK_AND_HOLD":
                duration = float(params[2]) if len(params) > 2 else 1.0
                x, y = _xy(0, 1)
                click_and_hold(x, y, duration)
            elif action_name == "SHIFT_CLICK":
                x, y = _xy(0, 1)
                shift_click(x, y)
            elif action_name == "CTRL_CLICK":
                x, y = _xy(0, 1)
                ctrl_click(x, y)
            elif action_name == "ALT_CLICK":
                x, y = _xy(0, 1)
                alt_click(x, y)
            elif action_name == "TYPE":
                type_text(params[0])
            elif action_name == "TYPE_UNICODE":
                type_unicode(params[0])
            elif action_name == "CLEAR_FIELD":
                x, y = _xy(0, 1)
                clear_field(x, y)
            elif action_name == "PRESS":
                press_key(params[0])
            elif action_name == "HOLD_KEY":
                duration = float(params[1]) if len(params) > 1 else 0.5
                hold_key(params[0], duration)
            elif action_name == "HOTKEY":
                hotkey(*params)
            elif action_name == "SCROLL":
                scroll(int(params[0]))
            elif action_name == "SCROLL_AT":
                x, y = _xy(0, 1)
                scroll_at(x, y, int(params[2]))
            elif action_name == "HORIZONTAL_SCROLL":
                horizontal_scroll(int(params[0]))
            elif action_name == "DRAG":
                x1, y1 = _xy(0, 1)
                x2, y2 = _xy(2, 3)
                drag(x1, y1, x2, y2)
            elif action_name == "COPY":
                copy_to_clipboard()
            elif action_name == "PASTE":
                paste_from_clipboard()
            elif action_name == "SET_CLIPBOARD":
                set_clipboard(params[0])
            elif action_name == "SHELL":
                action_result = run_shell_command(params[0])
                if action_result:
                    print(f"Shell output: {action_result}")
            elif action_name == "OPEN_APP":
                success, method = open_app(params[0])
                if not success:
                    action_result = f"Failed to open app {params[0]}"
                    print(action_result)
                else:
                    action_result = f"App {params[0]} {method} successfully."
            elif action_name == "WAIT":
                # Cap wait time to 1 second max to prevent slowdowns
                wait_time = min(float(params[0]), 1.0)
                time.sleep(wait_time)
            elif action_name in ("MAXIMIZE_WINDOW", "MAXIMIZE_ACTIVE_WINDOW", "MAXIMIZE"):
                success, reason = maximize_active_window()
                if not success and reason not in ('already_maximized', 'skip_process'):
                    action_result = f"Maximize window: {reason}"
                    print(action_result)
            else:
                action_result = f"Unknown action: {action_name}"
                print(action_result)
            
            return action_result
            
        except Exception as e:
            error_msg = f"Error executing action {action_name}: {e}"
            print(error_msg)
            return error_msg

if __name__ == "__main__":
    # This is for testing
    agent = ComputerUseAgent()
    # agent.run_task("Open the calculator and calculate 5 + 5")
