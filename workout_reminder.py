#!/Users/mindcrank/Projects/workout-reminder/.venv/bin/python3
"""
Hourly Workout Reminder - a lightweight system tray app for Mac & PC.

Features:
- Runs in your system tray (menu bar on Mac, taskbar tray on Windows)
- Pings you every hour (configurable) with a popup + sound
- Lets you pick your own audio file (mp3/wav) to play
- Lets you edit the reminder message text
- Pause/Resume, Snooze, and Quit from the tray menu
- Remembers your settings between runs (~/.workout_reminder_config.json)

Install dependencies first (see requirements.txt / instructions below):
    pip install pystray pillow pygame

Run it:
    python workout_reminder.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw
import pygame

# Dialogs are implemented per-platform: native AppleScript on macOS (see
# _mac_ask_integer/_mac_choose_file below), tkinter on Windows. This isn't
# just style — Tk itself is broken on recent macOS releases (both the old
# system Tk and the latest Homebrew Tk crash creating a window), so macOS
# doesn't import tkinter at all rather than risk it.
IS_MAC = sys.platform == "darwin"

if not IS_MAC:
    import tkinter as tk
    from tkinter import filedialog, simpledialog

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".workout_reminder_config.json")

DEFAULT_CONFIG = {
    "interval_minutes": 60,
    "sound_path": None,   # None = fall back to system beep
    "message": "Time to get up and move! Do some push ups 💪",
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Could not save config: {e}")


# ---------- macOS native dialogs (AppleScript via osascript) ----------

def _applescript_string(s: str) -> str:
    """Quote a Python string as an AppleScript string literal."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _mac_ask_integer(title: str, prompt: str, initial: int) -> int | None:
    script = (
        f"display dialog {_applescript_string(prompt)} "
        f"with title {_applescript_string(title)} "
        f"default answer {_applescript_string(str(initial))}"
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return None  # user hit Cancel, or the dialog errored
    for part in result.stdout.strip().split(", "):
        if part.startswith("text returned:"):
            try:
                return int(part.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def _mac_ask_string(title: str, prompt: str, initial: str) -> str | None:
    script = (
        f"display dialog {_applescript_string(prompt)} "
        f"with title {_applescript_string(title)} "
        f"default answer {_applescript_string(initial)}"
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return None  # user hit Cancel, or the dialog errored
    marker = "text returned:"
    idx = result.stdout.find(marker)
    if idx == -1:
        return None
    return result.stdout[idx + len(marker):].strip()


def _mac_choose_file(prompt: str) -> str | None:
    script = f"POSIX path of (choose file with prompt {_applescript_string(prompt)})"
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return None  # user hit Cancel, or the dialog errored
    return result.stdout.strip() or None


class ReminderApp:
    def __init__(self):
        self.config = load_config()
        self.paused = False
        self.snooze_until = 0
        self.next_trigger_time = time.time() + self.config["interval_minutes"] * 60
        self.stop_flag = False

        pygame.mixer.init()

        self.icon = pystray.Icon(
            "workout_reminder",
            self.make_icon_image(),
            "Workout Reminder",
            menu=self.build_menu(),
        )

        # Only the Windows path needs this: tray menu callbacks fire on
        # pystray's own thread, but tkinter dialogs need to run on the main
        # thread. So the tray thread only ever queues a request; the Tk
        # mainloop below (on the main thread) polls the queue and opens the
        # actual dialog itself. macOS dialogs are separate osascript
        # subprocesses, so they need none of this and can run directly from
        # the tray callback thread.
        if not IS_MAC:
            self.dialog_queue = queue.Queue()
            self.root = tk.Tk()
            self.root.withdraw()

    # ---------- Tray icon ----------

    def make_icon_image(self, active=True):
        # Simple flexed-bicep-ish icon: a circle with a dumbbell line.
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = (46, 204, 113, 255) if active and not self.paused else (149, 165, 166, 255)
        draw.ellipse((4, 4, size - 4, size - 4), fill=color)
        draw.rectangle((18, 30, 46, 34), fill=(255, 255, 255, 255))
        draw.ellipse((12, 24, 24, 40), fill=(255, 255, 255, 255))
        draw.ellipse((40, 24, 52, 40), fill=(255, 255, 255, 255))
        return img

    def build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: "Resume" if self.paused else "Pause",
                self.toggle_pause,
            ),
            pystray.MenuItem("Snooze 10 min", self.snooze),
            pystray.MenuItem("Trigger now (test)", self.trigger_now),
            pystray.MenuItem("Set interval...", self.set_interval),
            pystray.MenuItem("Choose sound...", self.choose_sound),
            pystray.MenuItem("Edit message...", self.edit_message),
            pystray.MenuItem("Quit", self.quit_app),
        )

    def refresh_icon(self):
        self.icon.icon = self.make_icon_image()
        self.icon.menu = self.build_menu()

    # ---------- Menu actions ----------

    def toggle_pause(self, icon=None, item=None):
        self.paused = not self.paused
        if not self.paused:
            self.next_trigger_time = time.time() + self.config["interval_minutes"] * 60
        self.refresh_icon()

    def snooze(self, icon=None, item=None):
        self.next_trigger_time = time.time() + 10 * 60
        self.icon.notify("Snoozed for 10 minutes.", "Workout Reminder")

    def trigger_now(self, icon=None, item=None):
        threading.Thread(target=self.fire_reminder, daemon=True).start()

    def set_interval(self, icon=None, item=None):
        if IS_MAC:
            self._do_set_interval()
        else:
            self.dialog_queue.put(self._do_set_interval)

    def choose_sound(self, icon=None, item=None):
        if IS_MAC:
            self._do_choose_sound()
        else:
            self.dialog_queue.put(self._do_choose_sound)

    def edit_message(self, icon=None, item=None):
        if IS_MAC:
            self._do_edit_message()
        else:
            self.dialog_queue.put(self._do_edit_message)

    def _do_set_interval(self):
        if IS_MAC:
            val = _mac_ask_integer(
                "Set Interval",
                "Remind me every how many minutes? (1-480)",
                self.config["interval_minutes"],
            )
        else:
            val = simpledialog.askinteger(
                "Set Interval",
                "Remind me every how many minutes?",
                initialvalue=self.config["interval_minutes"],
                minvalue=1,
                maxvalue=480,
                parent=self.root,
            )
        if val and 1 <= val <= 480:
            self.config["interval_minutes"] = val
            save_config(self.config)
            self.next_trigger_time = time.time() + self.config["interval_minutes"] * 60

    def _do_choose_sound(self):
        if IS_MAC:
            path = _mac_choose_file("Choose a sound file (mp3/wav/ogg):")
        else:
            path = filedialog.askopenfilename(
                title="Choose a sound file",
                filetypes=[("Audio files", "*.mp3 *.wav *.ogg"), ("All files", "*.*")],
                parent=self.root,
            )
        if path:
            self.config["sound_path"] = path
            save_config(self.config)
            self.icon.notify(f"Sound set to: {os.path.basename(path)}", "Workout Reminder")

    def _do_edit_message(self):
        if IS_MAC:
            text = _mac_ask_string(
                "Edit Message",
                "What should the reminder say?",
                self.config["message"],
            )
        else:
            text = simpledialog.askstring(
                "Edit Message",
                "What should the reminder say?",
                initialvalue=self.config["message"],
                parent=self.root,
            )
        if text:
            self.config["message"] = text
            save_config(self.config)
            self.icon.notify("Message updated.", "Workout Reminder")

    def _process_dialog_queue(self):
        try:
            while True:
                action = self.dialog_queue.get_nowait()
                action()
        except queue.Empty:
            pass
        if not self.stop_flag:
            self.root.after(150, self._process_dialog_queue)

    def quit_app(self, icon=None, item=None):
        self.stop_flag = True
        self.icon.stop()
        if not IS_MAC:
            self.root.after(0, self.root.quit)

    # ---------- Reminder logic ----------

    def play_sound(self):
        sound_path = self.config.get("sound_path")
        try:
            if sound_path and os.path.exists(sound_path):
                pygame.mixer.music.load(sound_path)
                pygame.mixer.music.play()
            else:
                # Fallback: terminal bell
                print("\a")
        except Exception as e:
            print(f"Could not play sound: {e}")

    def fire_reminder(self):
        self.play_sound()
        self.icon.notify(self.config["message"], "Workout Reminder")

    def timer_loop(self):
        while not self.stop_flag:
            time.sleep(1)
            if self.paused:
                continue
            if time.time() >= self.next_trigger_time:
                self.fire_reminder()
                self.next_trigger_time = time.time() + self.config["interval_minutes"] * 60

    def run(self):
        threading.Thread(target=self.timer_loop, daemon=True).start()
        if IS_MAC:
            # No tkinter mainloop competing for the main thread on macOS —
            # dialogs are separate osascript subprocesses — so the tray icon
            # can just own the main thread normally.
            self.icon.run()
        else:
            # run_detached() runs the tray icon's own event loop on a
            # background thread instead, freeing the true main thread for
            # tkinter's mainloop below.
            self.icon.run_detached()
            self.root.after(150, self._process_dialog_queue)
            self.root.mainloop()


if __name__ == "__main__":
    app = ReminderApp()
    app.run()
