import os
import time
import mss
import mss.tools
from PIL import Image, ImageDraw
from google import genai
from google.genai import types
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
from ui_inspector import get_ui_tree_summary
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are a Computer Use Agent with Agentic Vision. You have control over the user's computer screen and input devices.
Your goal is to help the user with their tasks by seeing the screen and performing actions.

AGENTIC VISION CAPABILITIES:
1. **Zoom and Inspect**: You can write Python code to crop parts of the screen if you need to see details (like small text or icons) more clearly. You can also rotate images if needed.
2. **Visual Math**: Use Python code execution to perform calculations on visual data (e.g., summing numbers in a table, counting items).
3. **Image Annotation**: You can annotate the screen to ground your reasoning or show what you are looking at.

To use these, just write the Python code. The results will be returned to you in the next turn.

Available actions:

MOUSE ACTIONS:
- CLICK(x, y): Left click at normalized coordinates (x, y).
- DOUBLE_CLICK(x, y): Double click at normalized coordinates (x, y). Good for opening files/apps.
- TRIPLE_CLICK(x, y): Triple click to select an entire line or paragraph.
- RIGHT_CLICK(x, y): Right click to open context menus.
- MIDDLE_CLICK(x, y): Middle click (opens links in new tab, paste in some terminals).
- MOVE_MOUSE(x, y): Move mouse without clicking (for hover effects, tooltips, dropdown menus).
- CLICK_AND_HOLD(x, y, duration): Click and hold for specified seconds (for drag menus, long press).
- SHIFT_CLICK(x, y): Shift+Click for range selection (select from last click to this point).
- CTRL_CLICK(x, y): Ctrl+Click for multi-selection or opening links in new tabs.
- ALT_CLICK(x, y): Alt+Click for special interactions.
- DRAG(x1, y1, x2, y2): Drag from (x1, y1) to (x2, y2). Good for moving windows, selecting text.

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
3. **AVOID LOOPS**: If you try the same click/selection twice and the UI does not change, STOP repeating it. Change strategy.
4. After typing a search query, PRESS('enter') to trigger the search.
5. Use SCROLL(-5) to scroll DOWN and SCROLL(5) to scroll UP.
6. **MAXIMIZE IMMEDIATELY**: After opening or focusing an app, call MAXIMIZE_WINDOW() FIRST before interacting with its content.
7. **AGENTIC VISION**: If you are unsure about a detail on the screen (e.g., reading a small price or a serial number), use your Python tool to zoom into that area.

Coordinates: Use normalized coordinates from 0 to 1000. 
(0, 0) is top-left, (1000, 1000) is bottom-right.
The screen has a red 10x10 grid overlay to help you align clicks.

UI METADATA:
You will receive a list of "Detected UI Elements". Use these coordinates for high precision clicking.

Format your response CONCISELY:
REASONING: [One sentence max]
ACTION: [Action1]
ACTION: [Action2]
...

Output multiple ACTIONs when they can be performed in sequence without seeing the screen.
Do NOT use WAIT unless the UI truly needs time to load (e.g., after opening an app).
"""

# Maximum context messages to keep (system prompt + recent exchanges)
MAX_CONTEXT_MESSAGES = 5

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
        
        self.client = None
        if 'gemini' in self.api_keys:
            self.client = genai.Client(api_key=self.api_keys['gemini'])
        
        self.xai_client = None
        if 'xai' in self.api_keys and self.api_keys['xai']:
            self.xai_client = OpenAI(
                api_key=self.api_keys['xai'],
                base_url="https://api.x.ai/v1",
            )
            
        self.width, self.height = get_screen_size()
        self.should_stop = False

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
            self.client = genai.Client(api_key=self.api_keys['gemini'])
        
        if 'xai' in self.api_keys and self.api_keys['xai']:
            self.xai_client = OpenAI(
                api_key=self.api_keys['xai'],
                base_url="https://api.x.ai/v1",
            )

    def update_model(self, model_name):
        self.model_name = model_name

    def capture_screen(self, sct):
        # Capture the entire screen using the provided mss instance
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        
        # Draw a semi-transparent grid overlay
        draw = ImageDraw.Draw(img, "RGBA")
        width, height = img.size
        
        step_x = width // 10
        step_y = height // 10
        
        # Draw vertical lines
        for i in range(1, 10):
            x = i * step_x
            draw.line([(x, 0), (x, height)], fill=(255, 0, 0, 80), width=1) # Made grid lighter
            
        # Draw horizontal lines
        for i in range(1, 10):
            y = i * step_y
            draw.line([(0, y), (width, y)], fill=(255, 0, 0, 80), width=1)

        # Increase max size for Agentic Vision (zooming)
        # Gemini 3 Flash can handle large images well
        max_size = 2048 # Increased from 1024 to allow better zooming
        if img.width > max_size:
            ratio = max_size / img.width
            img = img.resize((max_size, int(img.height * ratio)), Image.Resampling.BILINEar)
        
        return img

    def _track_usage(self, response, log_func):
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count or 0
            output_tokens = usage.candidates_token_count or 0
            
            # Gemini 3 Pricing: $0.50/1M input, $3.00/1M output
            current_cost = (input_tokens / 1_000_000) * 0.50 + (output_tokens / 1_000_000) * 3.00
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += current_cost
            self.save_usage()
            
            log_func(f"  [Usage] Input: {input_tokens}, Output: {output_tokens}, Cost: ${current_cost:.5f}")
            log_func(f"  [Total Usage] Input: {self.total_input_tokens}, Output: {self.total_output_tokens}, Total Cost: ${self.total_cost:.5f}")

    def run_task(self, user_instruction, logger=None, status_callback=None):
        def log(msg):
            if logger:
                logger(msg)
            else:
                print(msg)
        
        def update_status(status):
            if status_callback:
                status_callback(status)

        log(f"Starting task with Agentic Vision: {user_instruction}")
        self.should_stop = False
        
        # New SDK uses Content objects
        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=SYSTEM_PROMPT)]),
            types.Content(role="model", parts=[types.Part.from_text(text="Understood. I will use my Agentic Vision capabilities to help with your task.")])
        ]
        
        recent_scroll_count = 0
        SCROLL_LOOP_THRESHOLD = 3
        last_action_signature = None
        repeated_action_signature_count = 0
        consecutive_no_action_count = 0
        prev_screen_hash = None
        prev_actions_executed = 0
        unchanged_after_actions_count = 0
        STUCK_REPEAT_THRESHOLD = 3
        STUCK_UNCHANGED_THRESHOLD = 3
        UNCHANGED_HASH_DISTANCE_THRESHOLD = 3
        stuck_hint_cooldown = 0
        STUCK_HINT_COOLDOWN_TURNS = 3
        
        with mss.mss() as sct:
            while not self.should_stop:
                start_time = time.perf_counter()
                update_status("looking")
                log("Capturing screen...")
                img = self.capture_screen(sct)
                
                log("Extracting UI metadata...")
                ui_metadata = get_ui_tree_summary()

                # Loop detection
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
                
                # Convert PIL to bytes for the new SDK
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()
                
                user_parts = [
                    types.Part.from_text(text=f"Task: {user_instruction}\n\n{ui_metadata}\n\nCurrent screen state is attached. What are the next actions?"),
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                ]
                history.append(types.Content(role="user", parts=user_parts))
                
                if len(history) > MAX_CONTEXT_MESSAGES + 1: # +1 for system prompt pair
                    history = [history[0], history[1]] + history[-(MAX_CONTEXT_MESSAGES - 1):]
                    log(f"  [Context] Pruned history to {len(history)} items")
                
                try:
                    update_status("thinking")
                    log(f"Sending to {self.model_name} (Agentic Vision enabled)...")
                    api_start = time.perf_counter()
                    
                    if self.model_name.startswith('grok'):
                        # Keep Grok support if needed, but here we focus on Gemini
                        # (Grok code remains similar but needs to adapt to history structure if used)
                        pass 
                    
                    # Gemini call with Code Execution
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=history,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(code_execution=types.ToolCodeExecution)],
                            temperature=0.0
                        )
                    )
                    self._track_usage(response, log)
                    
                    api_end = time.perf_counter()
                    log(f"  [Time] API: {api_end - api_start:.3f}s")
                    
                    # The response can have multiple parts
                    response_text = ""
                    executable_code = ""
                    code_result = ""
                    images_from_model = []
                    
                    model_parts = []
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            response_text += part.text + "\n"
                            model_parts.append(types.Part.from_text(text=part.text))
                        if part.executable_code:
                            executable_code = part.executable_code.code
                            log(f"  [Agentic Vision] Model is running code:\n{executable_code}")
                            model_parts.append(part)
                        if part.code_execution_result:
                            code_result = part.code_execution_result.output
                            log(f"  [Agentic Vision] Code result: {code_result}")
                            model_parts.append(part)
                        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.mime_type.startswith('image/'):
                             images_from_model.append(part)
                             model_parts.append(part)
                    
                    if response_text:
                        log(f"Agent Response:\n{response_text}")
                    
                    history.append(types.Content(role="model", parts=model_parts))
                    
                    # Execute all actions found in the response_text
                    actions_executed = 0
                    execution_start = time.perf_counter()
                    action_results = []
                    is_done = False

                    action_lines = [l.strip() for l in response_text.splitlines() if l.strip().upper().startswith("ACTION:") and "DONE" not in l.upper()]
                    action_signature = "\n".join(action_lines)

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

                    stuck_repeat = repeated_action_signature_count >= STUCK_REPEAT_THRESHOLD
                    stuck_unchanged = unchanged_after_actions_count >= STUCK_UNCHANGED_THRESHOLD
                    stuck_no_actions = not action_signature and consecutive_no_action_count >= 2
                    
                    if (stuck_repeat or stuck_unchanged or stuck_no_actions) and stuck_hint_cooldown == 0:
                        hint = "SYSTEM HINT: You appear stuck. Try a different approach or use your Agentic Vision (Python code) to zoom and inspect the UI if it's unclear."
                        history.append(types.Content(role="user", parts=[types.Part.from_text(text=hint)]))
                        log("  [Hint] Injected stuck-loop correction hint")
                        stuck_hint_cooldown = STUCK_HINT_COOLDOWN_TURNS

                    skip_actions_this_turn = stuck_repeat and stuck_unchanged
                    
                    for line in response_text.splitlines():
                        if self.should_stop: break
                        line_upper = line.strip().upper()
                        if line_upper.startswith("ACTION:"):
                            if "DONE" in line_upper:
                                log("Task completed signal received.")
                                update_status("done")
                                is_done = True
                                continue
                            if skip_actions_this_turn: continue
                                
                            log(f"  > {line.strip()}")
                            # Update status
                            act = line_upper
                            if "CLICK" in act or "DRAG" in act: update_status("clicking")
                            elif "TYPE" in act: update_status("typing")
                            elif "SCROLL" in act: update_status("scrolling")
                            elif "WAIT" in act: update_status("waiting")
                            else: update_status("acting")
                            
                            result = self.execute_action(line)
                            if result: action_results.append(result)
                            actions_executed += 1
                            time.sleep(0.05)
                    
                    if action_results:
                        res_text = "Action results:\n" + "\n".join(action_results)
                        history.append(types.Content(role="user", parts=[types.Part.from_text(text=res_text)]))
                    
                    if is_done: break
                    
                    prev_actions_executed = actions_executed
                    time.sleep(0.1)
                    
                except Exception as e:
                    log(f"Error during agent execution: {e}")
                    import traceback
                    traceback.print_exc()
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

        action_result = None
        try:
            start_time = time.perf_counter()
            if action_name == "CLICK":
                click(int(params[0]), int(params[1]))
            elif action_name == "DOUBLE_CLICK":
                double_click(int(params[0]), int(params[1]))
            elif action_name == "TRIPLE_CLICK":
                triple_click(int(params[0]), int(params[1]))
            elif action_name == "RIGHT_CLICK":
                right_click(int(params[0]), int(params[1]))
            elif action_name == "MIDDLE_CLICK":
                middle_click(int(params[0]), int(params[1]))
            elif action_name == "MOVE_MOUSE":
                move_mouse(int(params[0]), int(params[1]))
            elif action_name == "CLICK_AND_HOLD":
                duration = float(params[2]) if len(params) > 2 else 1.0
                click_and_hold(int(params[0]), int(params[1]), duration)
            elif action_name == "SHIFT_CLICK":
                shift_click(int(params[0]), int(params[1]))
            elif action_name == "CTRL_CLICK":
                ctrl_click(int(params[0]), int(params[1]))
            elif action_name == "ALT_CLICK":
                alt_click(int(params[0]), int(params[1]))
            elif action_name == "TYPE":
                type_text(params[0])
            elif action_name == "TYPE_UNICODE":
                type_unicode(params[0])
            elif action_name == "CLEAR_FIELD":
                clear_field(int(params[0]), int(params[1]))
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
                scroll_at(int(params[0]), int(params[1]), int(params[2]))
            elif action_name == "HORIZONTAL_SCROLL":
                horizontal_scroll(int(params[0]))
            elif action_name == "DRAG":
                drag(int(params[0]), int(params[1]), int(params[2]), int(params[3]))
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
