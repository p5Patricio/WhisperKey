"""Ventana de configuración de WhisperKey via customtkinter."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable
from PIL import Image

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

from pynput import keyboard as kb

import queue
import threading
import numpy as np
import sounddevice as sd

from whisperkey import config as config_module
from whisperkey.history import clear, get_entries
from whisperkey.platform import get_platform

log = logging.getLogger(__name__)

_MODEL_OPTIONS_DISPLAY = [
    "Automático (Detección automática)",
    "Tiny (Muy rápido, ~1GB VRAM)",
    "Base (Rápido, ~1GB VRAM)",
    "Small (Recomendado, ~2GB VRAM)",
    "Medium (Preciso, ~5GB VRAM)",
    "Large-v3 (Máxima calidad, ~10GB VRAM)"
]
_MODEL_DISPLAY_TO_CFG = {
    "Automático (Detección automática)": "auto",
    "Tiny (Muy rápido, ~1GB VRAM)": "tiny",
    "Base (Rápido, ~1GB VRAM)": "base",
    "Small (Recomendado, ~2GB VRAM)": "small",
    "Medium (Preciso, ~5GB VRAM)": "medium",
    "Large-v3 (Máxima calidad, ~10GB VRAM)": "large-v3"
}
_MODEL_CFG_TO_DISPLAY = {v: k for k, v in _MODEL_DISPLAY_TO_CFG.items()}

_DEVICE_OPTIONS_DISPLAY = [
    "Automático (Detección automática)",
    "CUDA (GPU NVIDIA - Recomendado)",
    "CPU (Procesador - Lento)",
    "MPS (Apple Silicon macOS)"
]
_DEVICE_DISPLAY_TO_CFG = {
    "Automático (Detección automática)": "auto",
    "CUDA (GPU NVIDIA - Recomendado)": "cuda",
    "CPU (Procesador - Lento)": "cpu",
    "MPS (Apple Silicon macOS)": "mps"
}
_DEVICE_CFG_TO_DISPLAY = {v: k for k, v in _DEVICE_DISPLAY_TO_CFG.items()}

_COMPUTE_OPTIONS_DISPLAY = [
    "float16 (Máxima calidad - GPU potente)",
    "int8_float16 (Balanceado - Recomendado)",
    "int8 (Baja VRAM)",
    "float32 (Solo CPU / Depuración)"
]
_COMPUTE_DISPLAY_TO_CFG = {
    "float16 (Máxima calidad - GPU potente)": "float16",
    "int8_float16 (Balanceado - Recomendado)": "int8_float16",
    "int8 (Baja VRAM)": "int8",
    "float32 (Solo CPU / Depuración)": "float32"
}
_COMPUTE_CFG_TO_DISPLAY = {v: k for k, v in _COMPUTE_DISPLAY_TO_CFG.items()}
_POSITION_OPTIONS = ["bottom-right", "bottom-left", "top-right", "top-left"]


class _KeyCaptureDialog:
    """Diálogo modal que captura la siguiente tecla presionada."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, on_captured: Callable[[str], None]) -> None:
        self._on_captured = on_captured
        self._listener: kb.Listener | None = None

        self._window = tk.Toplevel(parent)
        self._window.title("Capturar tecla")
        self._window.geometry("300x120")
        self._window.resizable(False, False)
        self._window.transient(parent)
        self._window.grab_set()

        tk.Label(self._window, text="Presioná la tecla que querés asignar...", font=("Segoe UI", 12)).pack(pady=10)
        self._status = tk.Label(self._window, text="Esperando...", font=("Segoe UI", 10, "italic"), fg="gray")
        self._status.pack(pady=5)

        self._window.protocol("WM_DELETE_WINDOW", self._close)

        self._listener = kb.Listener(on_press=self._on_press)
        self._listener.start()

    def _on_press(self, key) -> None:
        try:
            key_str = key.char
        except AttributeError:
            key_str = str(key).replace("Key.", "")
        self._status.configure(text=f"Capturada: {key_str}")
        self._window.after(200, lambda: self._close(key_str))

    def _close(self, key_str: str | None = None) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._window.destroy()
        if key_str is not None:
            self._on_captured(key_str)


class SettingsGUI:
    """Ventana de configuración con pestañas (Modelo, Audio, Hotkeys, Overlay, Historial, Sistema).

    Si *customtkinter* no está disponible, la ventana no se crea.
    """

    def __init__(self, master: tk.Tk | None = None, config: dict | None = None) -> None:
        if ctk is None:
            log.warning("customtkinter no disponible; settings GUI desactivado")
            return

        self._config = config or config_module.load_config()
        self._master = master
        self._mic_test_thread = None
        self._stop_mic_test_event = threading.Event()

        self._window = ctk.CTkToplevel(master)
        self._window.title("Configuración de WhisperKey")
        self._window.geometry("650x520")
        self._window.resizable(False, False)
        if master is not None:
            self._window.transient(master)

        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        # Registrar callback de progreso de descarga
        try:
            from whisperkey.transcription import CustomProgressBar
            CustomProgressBar.register(self._on_download_progress)
        except ImportError:
            pass

    def _build_ui(self) -> None:
        """Construye la interfaz con tabs y botones."""
        assert ctk is not None

        # Mostrar el logo en la parte superior si existe
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
        has_logo = False
        if os.path.exists(logo_path):
            try:
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(60, 60)
                )
                self._logo_label = ctk.CTkLabel(self._window, text="", image=logo_image)
                self._logo_label.pack(pady=(15, 0))
                has_logo = True
            except Exception as e:
                log.warning("No se pudo cargar el logo en configuración: %s", e)

        if has_logo:
            self._window.geometry("650x585")
            self._tabview = ctk.CTkTabview(self._window, width=610, height=410, command=self._on_tab_change)
        else:
            self._tabview = ctk.CTkTabview(self._window, width=610, height=420, command=self._on_tab_change)
        self._tabview.pack(pady=10, padx=20, fill="both", expand=True)

        self._tabview.add("Modelo")
        self._tabview.add("Audio")
        self._tabview.add("Hotkeys")
        self._tabview.add("Overlay")
        self._tabview.add("Historial")
        self._tabview.add("Sistema")

        self._build_model_tab()
        self._build_audio_tab()
        self._build_hotkeys_tab()
        self._build_overlay_tab()
        self._build_history_tab()
        self._build_system_tab()

        btn_frame = ctk.CTkFrame(self._window, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="Guardar", command=self._on_save, width=120, fg_color="#2F855A", hover_color="#22543D").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancelar", command=self._on_cancel, width=120, fg_color="#4A5568", hover_color="#2D3748").pack(side="left", padx=10)

    def _update_model_info(self, _=None) -> None:
        model_name = _MODEL_DISPLAY_TO_CFG.get(self._model_combo.get(), "auto")
        device_name = _DEVICE_DISPLAY_TO_CFG.get(self._device_combo.get(), "auto")

        temp_config = {
            "model": {
                "name": model_name,
                "device": device_name,
            }
        }

        if model_name == "auto":
            from whisperkey.config import detect_optimal_model
            resolved = detect_optimal_model(temp_config)
            resolved_text = f"Automático (Detectado: {resolved.upper()})"
        else:
            resolved = model_name
            resolved_text = model_name.upper()

        downloaded = config_module.is_model_downloaded(resolved)
        if downloaded:
            status_text = "Descargado y listo"
            status_color = "#38A169"  # Green
        else:
            status_text = "Requiere descarga (se descargará al arrancar la app)"
            status_color = "#DD6B20"  # Orange

        self._model_info_lbl.configure(
            text=f"Modelo activo: {resolved_text}\nEstado: {status_text}",
            text_color=status_color
        )

    def _build_model_tab(self) -> None:
        """Pestaña Modelo: name, device, compute_type."""
        assert ctk is not None
        tab = self._tabview.tab("Modelo")
        model_cfg = self._config.get("model", {})

        ctk.CTkLabel(tab, text="Modelo Whisper:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self._model_combo = ctk.CTkComboBox(tab, values=_MODEL_OPTIONS_DISPLAY, width=320, command=self._update_model_info)
        self._model_combo.set(_MODEL_CFG_TO_DISPLAY.get(model_cfg.get("name", "auto"), _MODEL_CFG_TO_DISPLAY["auto"]))
        self._model_combo.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Dispositivo:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self._device_combo = ctk.CTkComboBox(tab, values=_DEVICE_OPTIONS_DISPLAY, width=320, command=self._update_model_info)
        self._device_combo.set(_DEVICE_CFG_TO_DISPLAY.get(model_cfg.get("device", "cuda"), _DEVICE_CFG_TO_DISPLAY["cuda"]))
        self._device_combo.grid(row=1, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Tipo de cómputo:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self._compute_combo = ctk.CTkComboBox(tab, values=_COMPUTE_OPTIONS_DISPLAY, width=320, command=self._update_model_info)
        self._compute_combo.set(_COMPUTE_CFG_TO_DISPLAY.get(model_cfg.get("compute_type", "int8_float16"), _COMPUTE_CFG_TO_DISPLAY["int8_float16"]))
        self._compute_combo.grid(row=2, column=1, padx=10, pady=10)

        self._model_info_lbl = ctk.CTkLabel(
            tab,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            justify="left",
        )
        self._model_info_lbl.grid(row=3, column=0, columnspan=2, padx=10, pady=15, sticky="w")
        self._update_model_info()

        self._download_progress_lbl = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=11))
        self._download_progress_lbl.grid(row=4, column=0, columnspan=2, padx=10, pady=2, sticky="w")
        self._download_progress_lbl.grid_remove()

        self._download_progress_bar = ctk.CTkProgressBar(tab, width=320)
        self._download_progress_bar.set(0.0)
        self._download_progress_bar.grid(row=5, column=0, columnspan=2, padx=10, pady=2, sticky="w")
        self._download_progress_bar.grid_remove()

    def _build_audio_tab(self) -> None:
        """Pestaña Audio: sample_rate, channels, queue_maxsize, device, notification_sounds."""
        assert ctk is not None
        tab = self._tabview.tab("Audio")
        audio_cfg = self._config.get("audio", {})

        ctk.CTkLabel(tab, text="Sample rate (Hz):").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self._sample_rate = ctk.CTkEntry(tab, width=120)
        self._sample_rate.insert(0, str(audio_cfg.get("sample_rate", 16000)))
        self._sample_rate.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Canales:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self._channels = ctk.CTkEntry(tab, width=120)
        self._channels.insert(0, str(audio_cfg.get("channels", 1)))
        self._channels.grid(row=1, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Queue maxsize:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self._queue_maxsize = ctk.CTkEntry(tab, width=120)
        self._queue_maxsize.insert(0, str(audio_cfg.get("queue_maxsize", 100)))
        self._queue_maxsize.grid(row=2, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Micrófono:").grid(row=3, column=0, padx=10, pady=10, sticky="w")

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

        self._device_audio_combo = ctk.CTkComboBox(tab, values=input_devices, width=320)
        current_device = audio_cfg.get("device", "")
        if current_device and current_device in input_devices:
            self._device_audio_combo.set(current_device)
        else:
            self._device_audio_combo.set("Predeterminado del sistema")
        self._device_audio_combo.grid(row=3, column=1, padx=10, pady=10, columnspan=2, sticky="w")

        self._sounds_enabled = ctk.CTkCheckBox(tab, text="Habilitar sonidos de notificación")
        if audio_cfg.get("notification_sounds", True):
            self._sounds_enabled.select()
        self._sounds_enabled.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        self._mic_test_btn = ctk.CTkButton(tab, text="Probar micrófono", command=self._toggle_mic_test, width=150)
        self._mic_test_btn.grid(row=5, column=0, padx=10, pady=10, sticky="w")

        self._mic_level_bar = ctk.CTkProgressBar(tab, width=280)
        self._mic_level_bar.set(0.0)
        self._mic_level_bar.grid(row=5, column=1, padx=10, pady=10, sticky="w")

    def _build_hotkeys_tab(self) -> None:
        """Pestaña Hotkeys: ptt, toggle, load_model_key + captura."""
        assert ctk is not None
        tab = self._tabview.tab("Hotkeys")
        hotkeys_cfg = self._config.get("hotkeys", {})

        ctk.CTkLabel(tab, text="Push-to-Talk:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self._ptt_entry = ctk.CTkEntry(tab, width=180)
        self._ptt_entry.insert(0, hotkeys_cfg.get("ptt", "caps_lock"))
        self._ptt_entry.grid(row=0, column=1, padx=10, pady=10)
        ctk.CTkButton(tab, text="Capturar", width=80, command=lambda: self._capture_key(self._ptt_entry)).grid(row=0, column=2, padx=5)

        ctk.CTkLabel(tab, text="Toggle:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self._toggle_entry = ctk.CTkEntry(tab, width=180)
        self._toggle_entry.insert(0, hotkeys_cfg.get("toggle", "f10"))
        self._toggle_entry.grid(row=1, column=1, padx=10, pady=10)
        ctk.CTkButton(tab, text="Capturar", width=80, command=lambda: self._capture_key(self._toggle_entry)).grid(row=1, column=2, padx=5)

        ctk.CTkLabel(tab, text="Cargar modelo:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self._load_model_entry = ctk.CTkEntry(tab, width=180)
        self._load_model_entry.insert(0, hotkeys_cfg.get("load_model_key", ""))
        self._load_model_entry.grid(row=2, column=1, padx=10, pady=10)
        ctk.CTkButton(tab, text="Capturar", width=80, command=lambda: self._capture_key(self._load_model_entry)).grid(row=2, column=2, padx=5)

    def _build_overlay_tab(self) -> None:
        """Pestaña Overlay: enabled, position, opacity, font_size."""
        assert ctk is not None
        tab = self._tabview.tab("Overlay")
        overlay_cfg = self._config.get("overlay", {})

        self._overlay_enabled = ctk.CTkCheckBox(tab, text="Habilitar overlay")
        if overlay_cfg.get("enabled", True):
            self._overlay_enabled.select()
        self._overlay_enabled.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(tab, text="Posición:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self._position_combo = ctk.CTkComboBox(tab, values=_POSITION_OPTIONS, width=180)
        self._position_combo.set(overlay_cfg.get("position", "bottom-right"))
        self._position_combo.grid(row=1, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Opacidad:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self._opacity_slider = ctk.CTkSlider(tab, from_=0.1, to=1.0, number_of_steps=18, width=180)
        self._opacity_slider.set(overlay_cfg.get("opacity", 0.85))
        self._opacity_slider.grid(row=2, column=1, padx=10, pady=10)
        self._opacity_label = ctk.CTkLabel(tab, text=f"{self._opacity_slider.get():.2f}")
        self._opacity_label.grid(row=2, column=2, padx=5)
        self._opacity_slider.configure(command=lambda v: self._opacity_label.configure(text=f"{v:.2f}"))

        ctk.CTkLabel(tab, text="Tamaño de fuente:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self._font_size = ctk.CTkEntry(tab, width=120)
        self._font_size.insert(0, str(overlay_cfg.get("font_size", 14)))
        self._font_size.grid(row=3, column=1, padx=10, pady=10)

    def _build_history_tab(self) -> None:
        """Pestaña Historial: lista de transcripciones previas."""
        assert ctk is not None
        tab = self._tabview.tab("Historial")

        entries = get_entries(limit=100)

        ctk.CTkLabel(tab, text=f"Últimas {len(entries)} transcripciones", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5))

        scroll_frame = ctk.CTkScrollableFrame(tab, width=560, height=300)
        scroll_frame.pack(padx=10, pady=5, fill="both", expand=True)

        if not entries:
            ctk.CTkLabel(scroll_frame, text="Aún no hay transcripciones.", font=ctk.CTkFont(size=12)).pack(pady=20)
        else:
            for entry in entries:
                ts = entry.get("timestamp", "")[:19].replace("T", " ")
                text = entry.get("text", "")
                row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=ts, font=ctk.CTkFont(size=10), width=140).pack(side="left", padx=5)
                lbl = ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=11), anchor="w")
                lbl.pack(side="left", fill="x", expand=True, padx=5)
                ctk.CTkButton(row, text="📋", width=30, command=lambda t=text: self._copy_to_clipboard(t)).pack(side="right", padx=5)

        ctk.CTkButton(tab, text="Limpiar historial", command=self._clear_history, width=150).pack(pady=10)

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception as exc:
            log.warning("No se pudo copiar al clipboard: %s", exc)

    def _clear_history(self) -> None:
        clear()
        if self._window is not None:
            self._window.destroy()
            SettingsGUI(master=self._master, config=self._config)

    def _build_system_tab(self) -> None:
        """Pestaña Sistema: inicio automático y otras opciones."""
        assert ctk is not None
        tab = self._tabview.tab("Sistema")

        platform = get_platform()
        autostart_enabled = platform.is_autostart_enabled()

        self._autostart_var = tk.BooleanVar(value=autostart_enabled)
        self._autostart_check = ctk.CTkCheckBox(
            tab,
            text="Iniciar WhisperKey al encender el sistema",
            variable=self._autostart_var,
            onvalue=True,
            offvalue=False,
        )
        self._autostart_check.pack(pady=20, padx=20, anchor="w")

        ctk.CTkLabel(
            tab,
            text="Esto crea un lanzador en el directorio de inicio automático de tu sistema.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(pady=5, padx=20, anchor="w")

    def _capture_key(self, entry: ctk.CTkEntry) -> None:
        """Abre el diálogo de captura de tecla y escribe el resultado en *entry*."""
        if self._window is None:
            return

        def on_captured(key_str: str) -> None:
            entry.delete(0, "end")
            entry.insert(0, key_str)

        _KeyCaptureDialog(self._window, on_captured)

    def _on_save(self) -> None:
        """Persiste la configuración y muestra aviso de reinicio."""
        assert ctk is not None
        try:
            model_name = _MODEL_DISPLAY_TO_CFG.get(self._model_combo.get(), "auto")
            device_name = _DEVICE_DISPLAY_TO_CFG.get(self._device_combo.get(), "auto")
            compute_type = _COMPUTE_DISPLAY_TO_CFG.get(self._compute_combo.get(), "int8_float16")

            selected_audio_device = self._device_audio_combo.get()
            audio_device_val = "" if selected_audio_device == "Predeterminado del sistema" else selected_audio_device

            new_config = {
                "model": {
                    "name": model_name,
                    "device": device_name,
                    "compute_type": compute_type,
                },
                "audio": {
                    "sample_rate": int(self._sample_rate.get()),
                    "channels": int(self._channels.get()),
                    "queue_maxsize": int(self._queue_maxsize.get()),
                    "device": audio_device_val,
                    "notification_sounds": bool(self._sounds_enabled.get()),
                },
                "hotkeys": {
                    "ptt": self._ptt_entry.get(),
                    "toggle": self._toggle_entry.get(),
                    "load_model_key": self._load_model_entry.get(),
                },
                "overlay": {
                    "enabled": bool(self._overlay_enabled.get()),
                    "position": self._position_combo.get(),
                    "opacity": round(float(self._opacity_slider.get()), 2),
                    "font_size": int(self._font_size.get()),
                },
            }
            config_module.write_config(config_module.get_config_path(), new_config)

            # Sincronizar estado de sonido inmediatamente
            from whisperkey import sounds
            sounds.set_enabled(bool(self._sounds_enabled.get()))

            # Manejar inicio automático
            platform = get_platform()
            if getattr(self, "_autostart_var", None) is not None:
                if self._autostart_var.get():
                    platform.setup_autostart()
                else:
                    platform.remove_autostart()

            dialog = ctk.CTkToplevel(self._window)
            dialog.title("Configuración guardada")
            dialog.geometry("350x120")
            dialog.resizable(False, False)
            dialog.transient(self._window)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Reiniciar para aplicar cambios", font=ctk.CTkFont(size=14)).pack(pady=15)
            ctk.CTkButton(dialog, text="Aceptar", command=dialog.destroy, width=100).pack(pady=5)
        except Exception as exc:
            log.exception("Error al guardar configuración")
            dialog = ctk.CTkToplevel(self._window)
            dialog.title("Error")
            dialog.geometry("350x120")
            dialog.resizable(False, False)
            dialog.transient(self._window)
            dialog.grab_set()
            ctk.CTkLabel(dialog, text=f"Error: {exc}", font=ctk.CTkFont(size=12)).pack(pady=15)
            ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy, width=100).pack(pady=5)

    def _on_cancel(self) -> None:
        """Cierra la ventana sin guardar."""
        self._on_close()

    def _on_close(self) -> None:
        try:
            from whisperkey.transcription import CustomProgressBar
            CustomProgressBar.unregister(self._on_download_progress)
        except ImportError:
            pass
        self._stop_mic_test()
        if self._window is not None:
            self._window.destroy()

    def _on_tab_change(self) -> None:
        if self._tabview.get() != "Audio":
            self._stop_mic_test()

    def _on_download_progress(self, n: int, total: int, pct: float) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.after(0, lambda: self._update_progress_ui(n, total, pct))

    def _update_progress_ui(self, n: int, total: int, pct: float) -> None:
        if self._tabview.get() == "Modelo":
            self._download_progress_bar.grid()
            self._download_progress_lbl.grid()
            self._download_progress_bar.set(pct / 100.0)
            self._download_progress_lbl.configure(text=f"Descargando modelo: {pct:.1f}% ({n}/{total} bytes)")
            if pct >= 100.0:
                self._window.after(2000, self._hide_download_progress)

    def _hide_download_progress(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._download_progress_bar.grid_remove()
            self._download_progress_lbl.grid_remove()

    def _toggle_mic_test(self) -> None:
        if self._mic_test_thread is not None and self._mic_test_thread.is_alive():
            self._stop_mic_test()
        else:
            self._start_mic_test()

    def _start_mic_test(self) -> None:
        self._stop_mic_test_event.clear()
        self._mic_test_btn.configure(text="Detener Prueba")
        self._mic_test_thread = threading.Thread(target=self._run_mic_test, daemon=True)
        self._mic_test_thread.start()

    def _stop_mic_test(self) -> None:
        self._stop_mic_test_event.set()
        if self._mic_test_thread is not None:
            self._mic_test_thread = None
        if self._window is not None and self._window.winfo_exists():
            self._mic_test_btn.configure(text="Probar micrófono")
            self._mic_level_bar.set(0.0)

    def _run_mic_test(self) -> None:
        try:
            import time
            duration = 3.0
            samplerate = 16000
            channels = 1
            q = queue.Queue()

            def callback(indata, frames, time_info, status):
                if not self._stop_mic_test_event.is_set():
                    q.put(indata.copy())

            # Resolve selected mic
            selected_mic = self._device_audio_combo.get()
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
                start = time.time()
                while time.time() - start < duration and not self._stop_mic_test_event.is_set():
                    try:
                        data = q.get(timeout=0.1)
                        peak = float(np.max(np.abs(data)))
                        if self._window is not None and self._window.winfo_exists():
                            self._window.after(0, lambda v=peak: self._mic_level_bar.set(min(v, 1.0)))
                    except queue.Empty:
                        continue

            if not self._stop_mic_test_event.is_set():
                if self._window is not None and self._window.winfo_exists():
                    self._window.after(0, self._stop_mic_test)

        except Exception as exc:
            log.warning("Error en test de micrófono de configuración: %s", exc)
            if self._window is not None and self._window.winfo_exists():
                self._window.after(0, self._stop_mic_test)
