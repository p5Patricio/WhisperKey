"""Composition root de WhisperKey."""

from __future__ import annotations

import logging
import pathlib
import sys
import threading

from whisperkey import config as config_module
from whisperkey import sounds
from whisperkey.audio import start_stream, stop_stream
from whisperkey.hotkeys import start_listener
from whisperkey.injection import inject_text
from whisperkey.overlay import RecordingOverlay
from whisperkey.state import AppState
from whisperkey.transcription import load_model, transcription_worker, unload_model
from whisperkey.tray import start_tray

log = logging.getLogger(__name__)

try:
    import customtkinter as ctk

    _CTK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CTK_AVAILABLE = False


def main() -> None:
    # Ocultar consola en Windows cuando corre desde terminal normal
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # ------------------------------------------------------------------
    # Single Tk instance rule — root siempre oculto
    # ------------------------------------------------------------------
    if _CTK_AVAILABLE:
        root = ctk.CTk()
    else:
        import tkinter as tk

        root = tk.Tk()
    root.withdraw()

    config_path = pathlib.Path(config_module.get_config_path())
    first_run = config_module.is_first_run(str(config_path))

    try:
        config = config_module.load_config(str(config_path))
    except ValueError as exc:
        log.error("Configuración inválida: %s", exc)
        sys.exit(1)

    sounds.set_enabled(config["audio"].get("notification_sounds", True))

    if first_run and sys.platform == "darwin":
        log.warning(
            "macOS: Para que WhisperKey funcione correctamente, concedé permisos de "
            "Accesibilidad a la terminal/IDE desde la que se ejecuta "
            "(Preferencias del Sistema > Seguridad y Privacidad > Accesibilidad)."
        )

    log.info(
        "WhisperKey iniciando... PTT: %s | Toggle: %s",
        config["hotkeys"]["ptt"],
        config["hotkeys"]["toggle"],
    )

    # ------------------------------------------------------------------
    # Onboarding (primer uso)
    # ------------------------------------------------------------------
    if first_run:
        if _CTK_AVAILABLE:
            from whisperkey.onboarding import OnboardingWizard

            OnboardingWizard(master=root)
        else:
            config_module.write_config(str(config_path), {"first_run": False})

    # ------------------------------------------------------------------
    # Chequeo de actualizaciones asincrónico
    # ------------------------------------------------------------------
    def _run_updater_check():
        try:
            from whisperkey.updater import check_update, show_update_dialog
            is_newer, version, url, changelog = check_update()
            if is_newer:
                log.info("Nueva versión disponible: %s", version)
                root.after(0, lambda: show_update_dialog(root, version, url, changelog))
        except Exception as exc:
            log.warning("No se pudo verificar actualizaciones: %s", exc)

    threading.Thread(target=_run_updater_check, daemon=True).start()

    queue_maxsize = config["audio"].get("queue_maxsize", 100)
    state = AppState(audio_queue_maxsize=queue_maxsize)
    overlay = RecordingOverlay(config)

    # ------------------------------------------------------------------
    # Splash screen
    # ------------------------------------------------------------------
    splash = None
    if _CTK_AVAILABLE:
        from whisperkey.splash import SplashScreen

        splash = SplashScreen(master=root)
        splash.set_status("Inicializando WhisperKey...")

    # 1. Transcription worker daemon
    worker = threading.Thread(
        target=transcription_worker,
        args=(state, config, inject_text, sounds),
        daemon=True,
    )
    worker.start()

    # 2. Model loader daemon
    def _load_with_splash() -> None:
        if splash is not None:
            splash.set_status("Cargando modelo Whisper...")
        try:
            load_model(state, config, sounds, overlay)
        except Exception:
            pass
        finally:
            if splash is not None:
                splash.close()

    loader = threading.Thread(
        target=_load_with_splash,
        daemon=True,
    )
    loader.start()

    # 3. Audio stream — siempre activo
    stream = start_stream(state, config, overlay)

    # 4. Keyboard listener
    listener = start_listener(state, config, overlay, sounds)

    # 5. Tray — daemon thread (no bloquea main thread)
    def _on_quit(icon) -> None:
        log.info("Iniciando shutdown...")
        state.shutdown_event.set()
        stop_stream(stream)
        listener.stop()
        state.put_sentinel()
        worker.join(timeout=5)
        if worker.is_alive():
            log.warning("transcription_worker no terminó en 5s")
        loader.join(timeout=5)
        if loader.is_alive():
            log.warning("loader no terminó en 5s")
        unload_model(state)
        overlay.destroy()
        if splash is not None:
            splash.close()
        root.after(0, root.destroy)
        icon.stop()

    def _do_load() -> None:
        threading.Thread(
            target=load_model,
            args=(state, config, sounds, overlay),
            daemon=True,
        ).start()

    tray_thread = threading.Thread(
        target=start_tray,
        args=(state, config),
        kwargs={
            "on_load": _do_load,
            "on_unload": lambda: unload_model(state),
            "on_quit": _on_quit,
            "master": root,
        },
        daemon=True,
        name="tray",
    )
    tray_thread.start()

    # Main thread corre el loop de tkinter
    try:
        root.mainloop()
    except KeyboardInterrupt:
        stop_stream(stream)

    log.info("WhisperKey finalizado.")


if __name__ == "__main__":
    main()
