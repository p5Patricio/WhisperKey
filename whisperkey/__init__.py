"""
WhisperKey — Voice-to-Text local para Windows.

Paquete principal que contiene todos los módulos del sistema:
- state: AppState dataclass con threading locks
- sounds: feedback auditivo via winsound
- injection: inyección de texto via pyperclip + pynput
- audio: captura de audio via sounddevice
- transcription: transcripción via faster-whisper
- hotkeys: listener de teclado via pynput
- tray: icono de bandeja via pystray
- overlay: overlay visual de grabación
"""
