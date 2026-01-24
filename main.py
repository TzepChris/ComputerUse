import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
from agent import ComputerUseAgent

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Gemini Computer Use Agent")
        self.root.geometry("600x600")
        self.root.attributes("-topmost", True) # Keep on top

        self.agent = None
        self.is_running = False
        self.emergency_root = None

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Model Selection
        ttk.Label(main_frame, text="Select Model:").pack(anchor=tk.W)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(main_frame, textvariable=self.model_var, state="readonly")
        self.model_combo['values'] = (
            'gemini-3-flash-preview',
        )
        self.model_combo.set('gemini-3-flash-preview')
        self.model_combo.pack(fill=tk.X, pady=5)

        # Instruction
        ttk.Label(main_frame, text="Instruction:").pack(anchor=tk.W)
        self.instruction_entry = tk.Text(main_frame, height=5)
        self.instruction_entry.pack(fill=tk.X, pady=5)
        self.instruction_entry.insert(tk.END, "Open Notepad and type 'Hello from Gemini!'")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.run_button = ttk.Button(button_frame, text="Run Agent", command=self.toggle_agent)
        self.run_button.pack(side=tk.LEFT, padx=5)

        self.clear_log_button = ttk.Button(button_frame, text="Clear Log", command=self.clear_log)
        self.clear_log_button.pack(side=tk.LEFT, padx=5)

        # Status
        self.status_label = ttk.Label(main_frame, text="Status: Idle")
        self.status_label.pack(pady=5)

        # Log Area
        ttk.Label(main_frame, text="Agent Log:").pack(anchor=tk.W)
        self.log_text = tk.Text(main_frame, height=15, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar for log
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(main_frame, text="Press Ctrl+C in terminal or close window to stop", foreground="gray").pack(side=tk.BOTTOM)

    def show_emergency_stop(self):
        if self.emergency_root:
            return
            
        self.emergency_root = tk.Toplevel() # Independent from self.root to stay visible when minimized
        self.emergency_root.attributes("-topmost", True)
        self.emergency_root.overrideredirect(True)
        
        # Modern frosted glass style - dark semi-transparent background
        bg_transparent = '#000001'
        bg_dark = '#1a1a1a'
        self.emergency_root.config(bg=bg_transparent)
        self.emergency_root.attributes("-transparentcolor", bg_transparent)
        self.emergency_root.attributes("-alpha", 0.92)
        
        # Position at top center
        screen_width = self.emergency_root.winfo_screenwidth()
        w = 320
        h = 110
        x = (screen_width // 2) - (w // 2)
        y = 30
        self.emergency_root.geometry(f"{w}x{h}+{x}+{y}")
        
        self.emergency_canvas = tk.Canvas(self.emergency_root, width=w, height=h, bg=bg_transparent, highlightthickness=0)
        self.emergency_canvas.pack(fill=tk.BOTH, expand=True)
        
        canvas = self.emergency_canvas
        
        # Rounded rectangle helper
        def create_rounded_rect(x1, y1, x2, y2, r, **kwargs):
            points = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
            return canvas.create_polygon(points, **kwargs, smooth=True)

        self.main_bg = create_rounded_rect(0, 0, w, h, 20, fill=bg_dark, outline='#333333', width=1)
        
        self.status_text = canvas.create_text(
            w//2,
            32,
            text="🧠 Thinking...",
            fill="#ffffff",
            font=("Segoe UI", 13),
        )
        
        canvas.create_line(20, 58, w-20, 58, fill='#3a3a3a', width=1)
        
        btn_y1, btn_y2 = 68, 98
        btn_x1, btn_x2 = w//2 - 60, w//2 + 60
        stop_color, stop_hover = "#e74c3c", "#ff6b5b"
        
        self.rect = create_rounded_rect(btn_x1, btn_y1, btn_x2, btn_y2, 15, fill=stop_color, outline='')
        self.text = canvas.create_text(
            w//2,
            (btn_y1 + btn_y2) // 2,
            text="STOP",
            fill="white",
            font=("Segoe UI", 12, "bold"),
        )
        
        def on_click(e):
            self.toggle_agent()
            
        def on_enter(e):
            canvas.itemconfig(self.rect, fill=stop_hover)
        def on_leave(e):
            canvas.itemconfig(self.rect, fill=stop_color)
            
        for item in (self.rect, self.text):
            canvas.tag_bind(item, "<Button-1>", on_click)
            canvas.tag_bind(item, "<Enter>", on_enter)
            canvas.tag_bind(item, "<Leave>", on_leave)
        
        # Draggable logic
        self._drag_data = {"x": 0, "y": 0}
        def start_drag(e):
            self._drag_data["x"] = e.x
            self._drag_data["y"] = e.y
        def drag(e):
            dx, dy = e.x - self._drag_data["x"], e.y - self._drag_data["y"]
            nx, ny = self.emergency_root.winfo_x() + dx, self.emergency_root.winfo_y() + dy
            self.emergency_root.geometry(f"+{nx}+{ny}")
        
        canvas.tag_bind(self.main_bg, "<Button-1>", start_drag)
        canvas.tag_bind(self.main_bg, "<B1-Motion>", drag)
        canvas.tag_bind(self.status_text, "<Button-1>", start_drag)
        canvas.tag_bind(self.status_text, "<B1-Motion>", drag)

        # Persistence Loop: Ensure it stays on top every 2 seconds
        def keep_topmost():
            if self.emergency_root:
                try:
                    self.emergency_root.attributes("-topmost", True)
                    self.emergency_root.lift()
                    self.emergency_root.after(2000, keep_topmost)
                except: pass
        keep_topmost()

    def update_agent_status(self, status):
        """Update the status display in the emergency stop overlay"""
        if self.emergency_root and hasattr(self, 'status_text') and hasattr(self, 'emergency_canvas') and self.emergency_canvas:
            status_map = {
                "thinking": "🧠 Thinking...",
                "looking": "👁️ Looking at screen...",
                "clicking": "🖱️ Clicking...",
                "typing": "⌨️ Typing...",
                "scrolling": "📜 Scrolling...",
                "waiting": "⏳ Waiting...",
                "acting": "⚡ Acting...",
                "done": "✅ Done!",
            }
            display_text = status_map.get(status.lower(), f"🔄 {status}")
            try:
                self.emergency_canvas.itemconfig(self.status_text, text=display_text)
                # If status is "done", ensure we stay visible
                if status.lower() == "done":
                    self.emergency_root.attributes("-topmost", True)
                    self.emergency_root.lift()
            except tk.TclError:
                pass

    def hide_emergency_stop(self):
        if self.emergency_root:
            self.emergency_root.destroy()
            self.emergency_root = None

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        print(message) # Keep console log too

    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def toggle_agent(self):
        gemini_key = os.environ.get("GOOGLE_API_KEY", "").strip()
        
        if not self.is_running:
            instruction = self.instruction_entry.get("1.0", tk.END).strip()
            if not instruction:
                messagebox.showwarning("Warning", "Please enter an instruction.")
                return

            model_name = self.model_var.get()
            
            # Check keys
            if not gemini_key:
                messagebox.showerror("Error", "Gemini API Key (GOOGLE_API_KEY) not found in environment.")
                return

            self.is_running = True
            self.run_button.config(text="Stop Agent")
            self.status_label.config(text="Status: Running...")
            self.log(f"--- Starting Task: {instruction} ---")
            
            # Show emergency stop button
            self.show_emergency_stop()
            
            # Minimize window to avoid obstructing the view
            self.root.iconify()
            
            # Initialize agent if needed
            api_keys = {"gemini": gemini_key}
            if not self.agent:
                self.agent = ComputerUseAgent(api_keys=api_keys, model_name=model_name)
            else:
                self.agent.update_api_keys(api_keys)
                self.agent.update_model(model_name)
            
            # Run agent in a separate thread
            self.agent_thread = threading.Thread(target=self.run_agent, args=(instruction,))
            self.agent_thread.daemon = True
            self.agent_thread.start()
        else:
            self.log("Stopping agent...")
            if self.agent:
                self.agent.stop()
            self.is_running = False
            self.run_button.config(text="Run Agent")
            self.status_label.config(text="Status: Idle")
            # Hide emergency stop button
            self.hide_emergency_stop()
            # Restore window
            self.root.deiconify()
            self.root.attributes("-topmost", True)

    def run_agent(self, instruction):
        try:
            # Small delay to ensure window is minimized before first screenshot
            time.sleep(0.5)
            # Pass a logger function and status callback to the agent
            def status_updater(status):
                self.root.after(0, lambda s=status: self.update_agent_status(s))
            self.agent.run_task(instruction, logger=self.log, status_callback=status_updater)
            
            self.root.after(0, self.on_task_complete)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"CRITICAL ERROR: {str(e)}"))
            self.root.after(0, self.on_task_complete)

    def on_task_complete(self):
        self.is_running = False
        self.run_button.config(text="Run Agent")
        self.status_label.config(text="Status: Idle")
        
        # Show "Done" state for a few seconds before disappearing
        self.update_agent_status("done")
        self.root.after(3000, self.hide_emergency_stop)
        
        # Restore main window
        self.root.deiconify()
        self.root.attributes("-topmost", True)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
