"""Ventana de configuración de WhisperKey via customtkinter."""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

from pynput import keyboard as kb

from whisperkey import config as config_module
from whisperkey.history import clear, get_entries
from whisperkey.platform import get_platform

log = logging.getLogger(__name__)

_MODEL_OPTIONS = ["auto", "tiny", "base", "small", "medium", "large-v3"]
_DEVICE_OPTIONS = ["auto", "cuda", "cpu", "mps"]
_COMPUTE_OPTIONS = ["float16", "int8_float16", "int8", "float32"]
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

        self._window = ctk.CTkToplevel(master)
        self._window.title("Configuración de WhisperKey")
        self._window.geometry("650x520")
        self._window.resizable(False, False)
        if master is not None:
            self._window.transient(master)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construye la interfaz con tabs y botones."""
        assert ctk is not None
        self._tabview = ctk.CTkTabview(self._window, width=610, height=420)
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

        ctk.CTkButton(btn_frame, text="Guardar", command=self._on_save, width=120).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancelar", command=self._on_cancel, width=120).pack(side="left", padx=10)

    def _build_model_tab(self) -> None:
        """Pestaña Modelo: name, device, compute_type."""
        assert ctk is not None
        tab = self._tabview.tab("Modelo")
        model_cfg = self._config.get("model", {})

        ctk.CTkLabel(tab, text="Modelo Whisper:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self._model_combo = ctk.CTkComboBox(tab, values=_MODEL_OPTIONS, width=200)
        self._model_combo.set(model_cfg.get("name", "auto"))
        self._model_combo.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Dispositivo:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self._device_combo = ctk.CTkComboBox(tab, values=_DEVICE_OPTIONS, width=200)
        self._device_combo.set(model_cfg.get("device", "cuda"))
        self._device_combo.grid(row=1, column=1, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Tipo de cómputo:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self._compute_combo = ctk.CTkComboBox(tab, values=_COMPUTE_OPTIONS, width=200)
        self._compute_combo.set(model_cfg.get("compute_type", "int8_float16"))
        self._compute_combo.grid(row=2, column=1, padx=10, pady=10)

    def _build_audio_tab(self) -> None:
        """Pestaña Audio: sample_rate, channels, queue_maxsize."""
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
            new_config = {
                "model": {
                    "name": self._model_combo.get(),
                    "device": self._device_combo.get(),
                    "compute_type": self._compute_combo.get(),
                },
                "audio": {
                    "sample_rate": int(self._sample_rate.get()),
                    "channels": int(self._channels.get()),
                    "queue_maxsize": int(self._queue_maxsize.get()),
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
            config_module.write_config("config.toml", new_config)

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
        if self._window is not None:
            self._window.destroy()
