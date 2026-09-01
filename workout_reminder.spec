# PyInstaller spec for Workout Reminder.
#
# LSUIElement=True hides the Dock icon and top menu bar (File/Edit/...) that
# a packaged macOS app normally gets — this is a menu-bar-only tray utility,
# so it should behave like one, not show up as a regular app.
#
# Build with:
#   .venv/bin/pyinstaller workout_reminder.spec
# Output: dist/Workout Reminder.app

a = Analysis(
    ['workout_reminder.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Workout Reminder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Workout Reminder',
)
app = BUNDLE(
    coll,
    name='Workout Reminder.app',
    icon=None,
    bundle_identifier='com.jackhatton.workoutreminder',
    info_plist={
        'LSUIElement': True,
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '',
    },
)
