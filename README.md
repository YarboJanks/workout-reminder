# Workout Reminder — Setup Guide

A tiny tray app that pings you every hour (or however often you set) to get up
and move, with a sound of your choosing.

## 1. Install Python

You need Python 3.9+ on both your Mac and PC.
- Mac: check with `python3 --version` in Terminal. If missing, install from python.org or `brew install python`.
  Mac dialogs (Set interval / Choose sound) use native AppleScript (`osascript`, built into macOS), not
  tkinter, so no extra Tk setup is needed.
- Windows: install from python.org (check "Add Python to PATH" during setup). Windows dialogs use tkinter,
  which ships with the standard Python installer — no extra install needed either.

## 2. Install dependencies

In a terminal, in the folder with these files:

```
pip install -r requirements.txt
```

(On Mac you may need `pip3` instead of `pip`.)

## 3. Run it

```
python workout_reminder.py
```

(On Mac: `python3 workout_reminder.py`)

You'll see a little green icon appear in your menu bar (Mac) or system tray
(Windows, may be in the hidden icons arrow). Click it for options:

- **Pause / Resume** — stop or restart the hourly pings
- **Snooze 10 min** — push the next reminder back
- **Trigger now (test)** — fire a reminder immediately, useful for testing your sound
- **Set interval...** — change how often it reminds you (default: 60 minutes)
- **Choose sound...** — pick any .mp3/.wav/.ogg file on your computer to play
- **Edit message...** — change the text the reminder notification shows
- **Quit** — close the app

Your interval and sound choice are saved automatically to
`~/.workout_reminder_config.json` and reloaded next time you start the app.

## 4. (Optional) Make it start automatically on work days

**Mac** — easiest way: use Automator or `launchd`. Simplest option: add the
run command to a shell script and use macOS's built-in **Shortcuts** app with
an automation, or just keep a Terminal alias/shortcut on your dock for
one-click launch on mornings you work from home.

**Windows** — create a `.bat` file with the run command, then use Windows
**Task Scheduler** to run it automatically on weekday mornings, or just pin it
to your Start Menu for a one-click launch.

If you'd like, I can write out the exact Task Scheduler / launchd setup for
automatic weekday starts — just ask.

## Notes

- If no sound file is chosen, it falls back to a simple terminal beep.
- The app runs quietly in the background; closing the terminal window will
  also close it unless you package it as a standalone app (see below).
- Mac dialogs are native AppleScript (`osascript`), not tkinter — Tk itself
  is broken on recent macOS releases (both the system Tk and the latest
  Homebrew Tk crash creating a window), so macOS never imports tkinter at
  all. Windows still uses tkinter, which works fine there.

## Packaging as a real double-click app

**Important: PyInstaller doesn't cross-compile.** A build only runs on the OS
it was built on — you have to build once on the Mac to get the `.app`, and
once on the PC to get the `.exe`. There's no way to produce both from one
machine.

### Mac

Already built — see `dist/Workout Reminder.app`. It's a real standalone app:
no terminal, no Dock icon (menu-bar only), quit it from the tray menu. Drag
it into `/Applications` to keep it somewhere permanent. To rebuild after
editing `workout_reminder.py` (e.g. you asked for a code change):

```
.venv/bin/pyinstaller workout_reminder.spec --noconfirm
rm -rf build
```

`workout_reminder.spec` sets `LSUIElement` so the built app never shows a
Dock icon — a plain `pyinstaller --onefile --windowed workout_reminder.py`
would work too, but you'd get a Dock icon since that flag isn't set outside
the spec file.

### Windows (PC)

Copy this whole project folder to your PC, then in a terminal there:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --onefile --windowed --name "Workout Reminder" workout_reminder.py
```

This produces `dist\Workout Reminder.exe` — a standalone double-click exe, no
terminal window, no Python install needed to run it afterward. `--windowed`
suppresses the console window the same way `--noconsole` would.
