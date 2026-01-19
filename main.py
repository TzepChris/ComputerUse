import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
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

        # API Keys
        ttk.Label(main_frame, text="Gemini API Key:").pack(anchor=tk.W)
        self.api_key_entry = ttk.Entry(main_frame, show="*")
        self.api_key_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(main_frame, text="X.AI API Key (for Grok):").pack(anchor=tk.W)
        self.xai_key_entry = ttk.Entry(main_frame, show="*")
        self.xai_key_entry.pack(fill=tk.X, pady=2)
        
        # Load keys from env if available
        import os
        gemini_key = os.environ.get("GOOGLE_API_KEY", "")
        if gemini_key:
            self.api_key_entry.insert(0, gemini_key)
        
        xai_key = os.environ.get("XAI_API_KEY", "")
        if xai_key:
            self.xai_key_entry.insert(0, xai_key)

        # Model Selection
        ttk.Label(main_frame, text="Select Model:").pack(anchor=tk.W)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(main_frame, textvariable=self.model_var, state="readonly")
        self.model_combo['values'] = (
            'gemini-3-flash-preview',
            'gemini-2.0-flash-thinking-exp-01-21',
            'gemini-2.0-flash',
            'grok-4-1-fast-non-reasoning'
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
            
        self.emergency_root = tk.Toplevel(self.root)
        self.emergency_root.attributes("-topmost", True)
        self.emergency_root.overrideredirect(True) # Remove title bar for a cleaner look
        
        # Position at top center
        screen_width = self.emergency_root.winfo_screenwidth()
        w, h = 250, 60
        x = (screen_width // 2) - (w // 2)
        y = 0
        self.emergency_root.geometry(f"{w}x{h}+{x}+{y}")
        
        # Styled panic button
        btn = tk.Button(
            self.emergency_root,
            text="🛑 EMERGENCY STOP",
            bg="#ff3333",
            fg="white",
            font=("Arial", 14, "bold"),
            command=self.toggle_agent,
            activebackground="#cc0000",
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            bd=0
        )
        btn.pack(fill=tk.BOTH, expand=True)
        
        # Add a small white border at the bottom
        border = tk.Frame(self.emergency_root, height=2, bg="white")
        border.pack(fill=tk.X, side=tk.BOTTOM)

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
        gemini_key = self.api_key_entry.get().strip()
        xai_key = self.xai_key_entry.get().strip()
        
        if not self.is_running:
            instruction = self.instruction_entry.get("1.0", tk.END).strip()
            if not instruction:
                messagebox.showwarning("Warning", "Please enter an instruction.")
                return

            model_name = self.model_var.get()
            
            # Check keys based on selected model
            if model_name.startswith('grok') and not xai_key:
                messagebox.showerror("Error", "Please enter your X.AI API Key for Grok models.")
                return
            elif not model_name.startswith('grok') and not gemini_key:
                messagebox.showerror("Error", "Please enter your Gemini API Key.")
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
            api_keys = {"gemini": gemini_key, "xai": xai_key}
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
            # Pass a logger function to the agent
            self.agent.run_task(instruction, logger=self.log)
            
            self.root.after(0, self.on_task_complete)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"CRITICAL ERROR: {str(e)}"))
            self.root.after(0, self.on_task_complete)

    def on_task_complete(self):
        self.is_running = False
        self.run_button.config(text="Run Agent")
        self.status_label.config(text="Status: Idle")
        # Hide emergency stop button
        self.hide_emergency_stop()
        # Restore window
        self.root.deiconify()
        self.root.attributes("-topmost", True) # Ensure it comes to front

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
