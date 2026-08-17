# WhisperKey Testing Checklist

## Pre-Release Testing

### 1. Fresh Install
- [ ] Download `WhisperKey-Setup.exe`
- [ ] Run installer on clean Windows system
- [ ] Verify installation completes without errors
- [ ] Verify Start Menu shortcut created
- [ ] Verify Desktop shortcut created (if selected)
- [ ] Verify app launches after installation

### 2. First Run (Onboarding)
- [ ] Onboarding wizard appears
- [ ] Step 1: Welcome screen displays correctly
- [ ] Step 2: Hardware detection works
- [ ] Step 3: Microphone test works
- [ ] Step 4: Hotkey capture works
- [ ] Step 5: Autostart option works
- [ ] Step 6: Tutorial displays correctly
- [ ] After onboarding, app runs normally

### 3. Config Migration
- [ ] First frozen run creates config in `%APPDATA%\WhisperKey\config.toml`
- [ ] Subsequent runs use same config
- [ ] Config survives uninstall/reinstall

### 4. Whisper.cpp Binaries
- [ ] `assets\bin\whisper-server.exe` exists after installation
- [ ] `assets\bin\cublas64_12.dll` exists (if CUDA build)
- [ ] `assets\bin\whisper.dll` exists
- [ ] Transcription works with whisper.cpp

### 5. Assets
- [ ] `assets\icons\tray_idle.png` exists
- [ ] `assets\icons\tray_ready.png` exists
- [ ] `assets\icons\tray_loading.png` exists
- [ ] `assets\icons\tray_error.png` exists
- [ ] `assets\logo.png` exists
- [ ] All icons display correctly in UI

### 6. Auto-Update
- [ ] App checks for updates on startup
- [ ] Update dialog appears when new version available
- [ ] "Update now" downloads installer
- [ ] SHA256 verification passes
- [ ] Silent install launches
- [ ] App exits and updates successfully
- [ ] Config preserved after update

### 7. Uninstall
- [ ] Uninstaller removes program files
- [ ] Uninstaller preserves `%APPDATA%\WhisperKey\` (user config)
- [ ] Option to delete config during uninstall works
- [ ] Start Menu shortcuts removed
- [ ] Desktop shortcuts removed
- [ ] Registry entry removed

### 8. Autostart
- [ ] Optional autostart during install works
- [ ] App launches at Windows startup
- [ ] Registry entry created in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

### 9. Error Handling
- [ ] No internet: update check fails gracefully
- [ ] SHA256 mismatch: update aborted with error
- [ ] Download failure: error message shown
- [ ] Installation failure: error message shown

### 10. Performance
- [ ] Fresh install completes in < 1 minute
- [ ] App launches in < 5 seconds
- [ ] Model loads in < 10 seconds
- [ ] Transcription latency < 2 seconds

### 11. Landing Page (web/)
- [ ] Scroll from hero through footer — Threads background stays fixed, doesn't scroll away
- [ ] "Descargar .exe" button resolves to a real, downloading asset (not a 404)
- [ ] Hero badge shows the live version fetched from GitHub (not the hardcoded fallback)
- [ ] All nav links scroll to the correct section, including Cómo Empezar and Documentación
- [ ] Responsive check at 375px width — no horizontal overflow, cards stack to 1 column
- [ ] Responsive check at 768px/1024px width — nav doesn't wrap or overflow
