# Gemini Computer Use Agent

A desktop application that uses Gemini 3 Flash to see your screen and perform actions based on your instructions.

## Prerequisites

- Python 3.10+
- A Google Gemini API Key

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your Google API Key:
   Create a `.env` file in the root directory and add:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

Run the application:
```bash
python main.py
```

Enter an instruction (e.g., "Find the latest news on Google") and click **Run Agent**.

## Features

- **Vision**: Uses Gemini 3 Flash to interpret screenshots.
- **Automation**: Can click, double-click, type, scroll, and drag.
- **Safety**: `pyautogui` failsafe is enabled. Move your mouse to any corner of the screen to stop the agent.

## Warning

This agent has full control over your computer. Use it with caution and never leave it unattended while it is running.
