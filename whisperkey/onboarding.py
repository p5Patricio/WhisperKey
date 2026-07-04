"""Asistente de primer uso (onboarding wizard) para WhisperKey."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from PIL import Image

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

import numpy as np
import sounddevice as sd
from pynput import keyboard as kb

from whisperkey import config as config_module
from whisperkey.platform import get_platform
from whisperkey.sounds import play_ready

log = logging.getLogger(__name__)

_STEP_TITLES = [
    "Bienvenido",
    "Hardware",
    "Micrófono",
    "Hotkeys",
    "Inicio automático",
    "Tutorial",
]


class OnboardingWizard:
    """Wizard de 5 pasos para configurar WhisperKey en el primer uso.

    Si *customtkinter* no está disponible, escribe ``first_run = false`` y retorna.
    """

    def __init__(self, master: tk.Tk | None = None) -> None:
        self._master = master
        self._current_step = 0
        self._captured_ptt_key: str = "caps_lock"
        self._recording_thread: threading.Thread | None = None
        self._stop_recording = threading.Event()

        if ctk is None:
            log.warning("customtkinter no disponible; saltando onboarding")
            self._mark_first_run_done()
            return

        self._window = ctk.CTkToplevel(master)
        self._window.title("Bienvenido a WhisperKey")
        self._window.geometry("600x450")
        self._window.resizable(False, False)
        if master is not None:
            self._window.transient(master)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._header = ctk.CTkLabel(
            self._window,
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self._header.pack(pady=(15, 5))

        self._step_label = ctk.CTkLabel(self._window, text="", font=ctk.CTkFont(size=12))
        self._step_label.pack(pady=(0, 10))

        self._content = ctk.CTkFrame(self._window, fg_color="transparent")
        self._content.pack(padx=20, pady=5, fill="both", expand=True)

        self._nav = ctk.CTkFrame(self._window, fg_color="transparent")
        self._nav.pack(pady=15)

        self._btn_prev = ctk.CTkButton(self._nav, text="Anterior", command=self._prev_step, width=100)
        self._btn_prev.pack(side="left", padx=10)

        self._btn_next = ctk.CTkButton(self._nav, text="Siguiente", command=self._next_step, width=100)
        self._btn_next.pack(side="left", padx=10)

        self._show_step(0)

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------

    def _show_step(self, idx: int) -> None:
        """Renderiza el paso *idx* (0-based)."""
        assert ctk is not None
        self._current_step = idx
        self._header.configure(text=_STEP_TITLES[idx])
        self._step_label.configure(text=f"Paso {idx + 1} de {len(_STEP_TITLES)}")

        for w in self._content.winfo_children():
            w.destroy()

        if idx == 0:
            self._build_step_welcome()
        elif idx == 1:
            self._build_step_hardware()
        elif idx == 2:
            self._build_step_mic()
        elif idx == 3:
            self._build_step_hotkeys()
        elif idx == 4:
            self._build_step_autostart()
        elif idx == 5:
            self._build_step_tutorial()

        self._btn_prev.configure(state="disabled" if idx == 0 else "normal")
        if idx == len(_STEP_TITLES) - 1:
            self._btn_next.configure(text="Empezar a usar WhisperKey")
        else:
            self._btn_next.configure(text="Siguiente")

    def _next_step(self) -> None:
        if self._current_step == len(_STEP_TITLES) - 1:
            self._apply_autostart()
            self._mark_first_run_done()
            self._window.destroy()
        else:
            self._show_step(self._current_step + 1)

    def _prev_step(self) -> None:
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _on_close(self) -> None:
        self._mark_first_run_done()
        self._window.destroy()

    def _mark_first_run_done(self) -> None:
        """Escribe ``first_run = false`` en config.toml."""
        config_path = Path(config_module.get_config_path())
        try:
            if config_path.exists():
                import tomllib
                with open(config_path, "rb") as f:
                    cfg = tomllib.load(f)
            else:
                cfg = {}
            if "app" not in cfg:
                cfg["app"] = {}
            cfg["app"]["first_run"] = False

            if "hotkeys" not in cfg:
                cfg["hotkeys"] = {}
            cfg["hotkeys"]["ptt"] = self._captured_ptt_key

            if "audio" not in cfg:
                cfg["audio"] = {}
            selected_mic = getattr(self, "_mic_combo", None)
            if selected_mic is not None:
                selected_val = selected_mic.get()
                cfg["audio"]["device"] = "" if selected_val == "Predeterminado del sistema" else selected_val

            sounds_var = getattr(self, "_sounds_var", None)
            if sounds_var is not None:
                cfg["audio"]["notification_sounds"] = sounds_var.get()

            config_module.write_config(str(config_path), cfg)
        except Exception as exc:
            log.warning("No se pudo marcar first_run como false: %s", exc)

    # ------------------------------------------------------------------
    # Step 1 — Welcome
    # ------------------------------------------------------------------

    def _build_step_welcome(self) -> None:
        assert ctk is not None
        import os
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(100, 100)
                )
                ctk.CTkLabel(self._content, text="", image=logo_image).pack(pady=(10, 0))
            except Exception as e:
                log.warning("No se pudo cargar el logo en onboarding: %s", e)

        ctk.CTkLabel(
            self._content,
            text="Bienvenido a WhisperKey",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=20)
        ctk.CTkLabel(
            self._content,
            text="Dictado por voz local, sin nube, bilingüe español/inglés.\n"
                 "Te guiaremos en unos pasos rápidos para configurar todo.",
            font=ctk.CTkFont(size=13),
            justify="center",
        ).pack(pady=10)

    # ------------------------------------------------------------------
    # Step 2 — Hardware
    # ------------------------------------------------------------------

    def _build_step_hardware(self) -> None:
        assert ctk is not None
        platform = get_platform()
        device, compute = platform.detect_gpu()

        try:
            import psutil
            total_ram = psutil.virtual_memory().total / (1024 ** 3)
            ram_text = f"{total_ram:.1f} GB"
        except Exception:
            ram_text = "No detectado"

        gpu_text = device.upper() if device != "cpu" else "CPU (sin GPU detectada)"
        recommended = config_module.detect_optimal_model({})

        ctk.CTkLabel(self._content, text="Detección de hardware", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkLabel(self._content, text=f"GPU / Dispositivo: {gpu_text}", font=ctk.CTkFont(size=13)).pack(pady=5)
        ctk.CTkLabel(self._content, text=f"RAM total: {ram_text}", font=ctk.CTkFont(size=13)).pack(pady=5)
        ctk.CTkLabel(
            self._content,
            text=f"Modelo recomendado: {recommended}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#2B6CB0",
        ).pack(pady=15)

    # ------------------------------------------------------------------
    # Step 3 — Mic Test
    # ------------------------------------------------------------------

    def _build_step_mic(self) -> None:
        assert ctk is not None
        self._mic_status = ctk.CTkLabel(self._content, text="Presioná el botón para probar tu micrófono", font=ctk.CTkFont(size=13))
        self._mic_status.pack(pady=10)

        # Selector de micrófono
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = ["Predeterminado del sistema"]
            for dev in devices:
                if dev["max_input_channels"] > 0:
                    name = dev["name"]
                    if name not in input_devices:
                        input_devices.append(name)
        except Exception:
            input_devices = ["Predeterminado del sistema"]

        ctk.CTkLabel(self._content, text="Seleccionar micrófono:", font=ctk.CTkFont(size=12)).pack(pady=(10, 2))
        self._mic_combo = ctk.CTkComboBox(self._content, values=input_devices, width=320)
        self._mic_combo.set("Predeterminado del sistema")
        self._mic_combo.pack(pady=2)

        self._volume_bar = ctk.CTkProgressBar(self._content, width=300)
        self._volume_bar.set(0)
        self._volume_bar.pack(pady=15)

        self._mic_btn = ctk.CTkButton(self._content, text="Probar micrófono (3s)", command=self._start_mic_test)
        self._mic_btn.pack(pady=10)

    def _start_mic_test(self) -> None:
        if self._recording_thread is not None and self._recording_thread.is_alive():
            return
        self._stop_recording.clear()
        self._mic_btn.configure(state="disabled")
        self._mic_status.configure(text="Grabando...")
        self._recording_thread = threading.Thread(target=self._record_3s, daemon=True)
        self._recording_thread.start()

    def _record_3s(self) -> None:
        """Graba 3 segundos y actualiza la barra de volumen."""
        try:
            duration = 3.0
            samplerate = 16000
            channels = 1
            q: queue.Queue = queue.Queue()

            def callback(indata, frames, time_info, status):  # noqa: ARG001
                if not self._stop_recording.is_set():
                    q.put(indata.copy())

            # Resolver dispositivo seleccionado
            selected_mic = self._mic_combo.get()
            device_id = None
            if selected_mic != "Predeterminado del sistema":
                try:
                    devices = sd.query_devices()
                    for idx, dev in enumerate(devices):
                        if dev["max_input_channels"] > 0 and selected_mic in dev["name"]:
                            device_id = idx
                            break
                except Exception:
                    pass

            with sd.InputStream(device=device_id, samplerate=samplerate, channels=channels, callback=callback):
                import time
                start = time.time()
                while time.time() - start < duration and not self._stop_recording.is_set():
                    try:
                        data = q.get(timeout=0.1)
                        peak = float(np.max(np.abs(data)))
                        if self._window is not None:
                            self._window.after(0, lambda v=peak: self._volume_bar.set(min(v, 1.0)))
                    except queue.Empty:
                        continue

            if not self._stop_recording.is_set():
                self._window.after(0, self._mic_test_done)
        except Exception as exc:
            log.warning("Error en test de micrófono: %s", exc)
            if self._window is not None:
                self._window.after(0, lambda: self._mic_status.configure(text=f"Error: {exc}"))
                self._window.after(0, lambda: self._mic_btn.configure(state="normal"))

    def _mic_test_done(self) -> None:
        self._mic_status.configure(text="¡Grabación exitosa!")
        self._mic_btn.configure(state="normal")
        self._volume_bar.set(0)
        play_ready()

    # ------------------------------------------------------------------
    # Step 4 — Hotkeys
    # ------------------------------------------------------------------

    def _build_step_hotkeys(self) -> None:
        assert ctk is not None
        ctk.CTkLabel(
            self._content,
            text="Presioná la tecla que querés usar para Push-to-Talk",
            font=ctk.CTkFont(size=13),
        ).pack(pady=10)

        self._hotkey_label = ctk.CTkLabel(
            self._content,
            text="Esperando...",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#2B6CB0",
        )
        self._hotkey_label.pack(pady=15)

        self._capture_btn = ctk.CTkButton(self._content, text="Capturar tecla", command=self._capture_ptt)
        self._capture_btn.pack(pady=10)

    def _capture_ptt(self) -> None:
        self._hotkey_label.configure(text="Presioná una tecla...")
        self._capture_btn.configure(state="disabled")

        listener: kb.Listener | None = None

        def on_press(key) -> None:
            nonlocal listener
            try:
                key_str = key.char
            except AttributeError:
                key_str = str(key).replace("Key.", "")
            self._captured_ptt_key = key_str
            if self._window is not None:
                self._window.after(0, lambda: self._hotkey_label.configure(text=f"Capturada: {key_str}"))
                self._window.after(0, lambda: self._capture_btn.configure(state="normal"))
            if listener is not None:
                listener.stop()

        listener = kb.Listener(on_press=on_press)
        listener.start()

    # ------------------------------------------------------------------
    # Step 5 — Autostart
    # ------------------------------------------------------------------

    def _build_step_autostart(self) -> None:
        assert ctk is not None
        ctk.CTkLabel(
            self._content,
            text="Preferencias de la aplicación",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=5)

        ctk.CTkLabel(
            self._content,
            text="Configurá las opciones iniciales del sistema y audio.",
            font=ctk.CTkFont(size=13),
            justify="center",
        ).pack(pady=5)

        self._autostart_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self._content,
            text="Iniciar WhisperKey automáticamente al encender el equipo",
            variable=self._autostart_var,
            onvalue=True,
            offvalue=False,
        ).pack(pady=10)

        self._sounds_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self._content,
            text="Habilitar sonidos de notificación",
            variable=self._sounds_var,
            onvalue=True,
            offvalue=False,
        ).pack(pady=10)

    def _apply_autostart(self) -> None:
        """Aplica la preferencia de inicio automático si el usuario la seleccionó."""
        if getattr(self, "_autostart_var", None) is not None and self._autostart_var.get():
            try:
                platform = get_platform()
                platform.setup_autostart()
            except Exception as exc:
                log.warning("No se pudo configurar inicio automático: %s", exc)

    # ------------------------------------------------------------------
    # Step 6 — Tutorial
    # ------------------------------------------------------------------

    def _build_step_tutorial(self) -> None:
        assert ctk is not None
        ctk.CTkLabel(
            self._content,
            text="¡Listo para usar WhisperKey!",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=10)

        instructions = (
            "• Mantené presionada la tecla PTT mientras hablás.\n"
            "• O presioná la tecla Toggle para iniciar/detener grabación.\n"
            "• El texto se pegará automáticamente en la app activa.\n"
            "• Usá el ícono de la bandeja para cargar/descargar el modelo.\n"
            "• Abrí Configuración desde la bandeja para personalizar todo."
        )
        ctk.CTkLabel(
            self._content,
            text=instructions,
            font=ctk.CTkFont(size=13),
            justify="left",
        ).pack(pady=10)
