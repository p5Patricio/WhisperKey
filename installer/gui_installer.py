"""Instalador gráfico standalone para WhisperKey."""

from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import sys
import threading
import tkinter as tk
from typing import Callable

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

from whisperkey import config as config_module
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


class InstallerWizard:
    """Wizard de instalación de 5 pasos.

    Si *customtkinter* no está disponible, usa tkinter estándar.
    """

    def __init__(self) -> None:
        self._current_step = 0
        self._selected_model = "base"
        self._selected_device = "auto"
        self._selected_compute = "int8_float16"
        self._install_thread: threading.Thread | None = None

        if ctk is not None:
            self._root = ctk.CTk()
        else:
            self._root = tk.Tk()
        self._root.title("Instalador de WhisperKey")
        self._root.geometry("600x500")
        self._root.resizable(False, False)

        self._header = self._create_label(self._root, "", font_size=18, bold=True)
        self._header.pack(pady=(15, 5))

        self._step_label = self._create_label(self._root, "", font_size=12)
        self._step_label.pack(pady=(0, 10))

        self._content = self._create_frame(self._root)
        self._content.pack(padx=20, pady=5, fill="both", expand=True)

        self._nav = self._create_frame(self._root)
        self._nav.pack(pady=15)

        self._btn_prev = self._create_button(self._nav, "Anterior", self._prev_step, width=100)
        self._btn_prev.pack(side="left", padx=10)

        self._btn_next = self._create_button(self._nav, "Siguiente", self._next_step, width=100)
        self._btn_next.pack(side="left", padx=10)

        self._show_step(0)
        self._root.mainloop()

    def _auto_finish_and_launch(self) -> None:
        self._launch_app()
        self._root.destroy()

    # ------------------------------------------------------------------
    # Helpers de widgets compatibles
    # ------------------------------------------------------------------

    def _create_label(self, parent, text: str, font_size: int = 13, bold: bool = False):
        if ctk is not None:
            weight = "bold" if bold else "normal"
            return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=font_size, weight=weight))
        return tk.Label(parent, text=text, font=("Segoe UI", font_size, "bold" if bold else "normal"))

    def _create_frame(self, parent):
        if ctk is not None:
            return ctk.CTkFrame(parent, fg_color="transparent")
        return tk.Frame(parent)

    def _create_button(self, parent, text: str, command: Callable | None = None, width: int = 100):
        if ctk is not None:
            return ctk.CTkButton(parent, text=text, command=command, width=width)
        return tk.Button(parent, text=text, command=command, width=width // 10)

    def _create_combo(self, parent, values: list[str], width: int = 200):
        if ctk is not None:
            return ctk.CTkComboBox(parent, values=values, width=width)
        combo = tk.ttk.Combobox(parent, values=values, width=width // 10, state="readonly")
        return combo

    def _create_entry(self, parent, width: int = 200):
        if ctk is not None:
            return ctk.CTkEntry(parent, width=width)
        return tk.Entry(parent, width=width // 10)

    def _create_progress(self, parent, width: int = 400):
        if ctk is not None:
            bar = ctk.CTkProgressBar(parent, width=width)
            bar.set(0)
            return bar
        import tkinter.ttk as ttk
        bar = ttk.Progressbar(parent, length=width, mode="determinate")
        return bar

    def _set_progress(self, bar, value: float) -> None:
        if ctk is not None:
            bar.set(value)
        else:
            bar["value"] = value * 100

    def _create_text(self, parent, width: int = 50, height: int = 10):
        if ctk is not None:
            return ctk.CTkTextbox(parent, width=width * 10, height=height * 20)
        return tk.Text(parent, width=width, height=height)

    def _text_insert(self, widget, text: str) -> None:
        if ctk is not None:
            widget.insert("end", text + "\n")
        else:
            widget.insert("end", text + "\n")
            widget.see("end")

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------

    def _show_step(self, idx: int) -> None:
        self._current_step = idx
        titles = ["Bienvenido", "Hardware", "Modelo", "Instalación"]
        self._header.configure(text=titles[idx])
        self._step_label.configure(text=f"Paso {idx + 1} de {len(titles)}")

        for w in self._content.winfo_children():
            w.destroy()

        if idx == 0:
            self._build_step_welcome()
        elif idx == 1:
            self._build_step_hardware()
        elif idx == 2:
            self._build_step_model()
        elif idx == 3:
            self._build_step_install()

        self._btn_prev.configure(state="disabled" if idx == 0 else "normal")
        if idx == 3:
            self._btn_next.configure(text="Cerrar", state="disabled")
        else:
            self._btn_next.configure(text="Siguiente")

    def _next_step(self) -> None:
        if self._current_step == 3:
            self._auto_finish_and_launch()
        elif self._current_step == 2:
            # BUG FIX: read values from dropdowns before moving to progress
            self._selected_model = _MODEL_DISPLAY_TO_CFG.get(self._model_combo.get(), "base")
            self._selected_device = _DEVICE_DISPLAY_TO_CFG.get(self._device_combo.get(), "auto")
            self._selected_compute = _COMPUTE_DISPLAY_TO_CFG.get(self._compute_combo.get(), "int8_float16")
            self._show_step(self._current_step + 1)
        else:
            self._show_step(self._current_step + 1)

    def _prev_step(self) -> None:
        if self._current_step > 0 and self._current_step != 3:
            self._show_step(self._current_step - 1)

    # ------------------------------------------------------------------
    # Step 1 — Welcome
    # ------------------------------------------------------------------

    def _build_step_welcome(self) -> None:
        self._create_label(self._content, "Bienvenido al instalador de WhisperKey", font_size=18, bold=True).pack(pady=20)
        self._create_label(
            self._content,
            "Este asistente instalará WhisperKey en tu sistema.\n"
            "Se creará un entorno virtual, se instalarán las dependencias\n"
            "y se generará un lanzador para iniciar la aplicación.",
            font_size=13,
        ).pack(pady=10)

    # ------------------------------------------------------------------
    # Step 2 — Hardware
    # ------------------------------------------------------------------

    def _build_step_hardware(self) -> None:
        platform = get_platform()
        device, _ = platform.detect_gpu()

        try:
            import psutil
            total_ram = psutil.virtual_memory().total / (1024 ** 3)
            ram_text = f"{total_ram:.1f} GB"
        except Exception:
            ram_text = "No detectado"

        try:
            recommended = config_module.detect_optimal_model({})
        except Exception:
            recommended = "base"

        self._selected_device = device
        self._selected_model = recommended

        self._create_label(self._content, "Detección de hardware", font_size=16, bold=True).pack(pady=10)
        self._create_label(self._content, f"Dispositivo detectado: {device.upper()}", font_size=13).pack(pady=5)
        self._create_label(self._content, f"RAM total: {ram_text}", font_size=13).pack(pady=5)
        self._create_label(self._content, f"Modelo recomendado: {recommended}", font_size=13, bold=True).pack(pady=15)

    # ------------------------------------------------------------------
    # Step 3 — Model selection
    # ------------------------------------------------------------------

    def _build_step_model(self) -> None:
        self._create_label(self._content, "Configuración del modelo", font_size=16, bold=True).pack(pady=10)

        self._create_label(self._content, "Modelo Whisper:").pack(pady=(10, 2))
        self._model_combo = self._create_combo(self._content, _MODEL_OPTIONS_DISPLAY, width=320)
        self._model_combo.set(_MODEL_CFG_TO_DISPLAY.get(self._selected_model, _MODEL_CFG_TO_DISPLAY["base"]))
        self._model_combo.pack(pady=2)

        self._create_label(self._content, "Dispositivo:").pack(pady=(10, 2))
        self._device_combo = self._create_combo(self._content, _DEVICE_OPTIONS_DISPLAY, width=320)
        self._device_combo.set(_DEVICE_CFG_TO_DISPLAY.get(self._selected_device, _DEVICE_CFG_TO_DISPLAY["auto"]))
        self._device_combo.pack(pady=2)

        self._create_label(self._content, "Tipo de cómputo:").pack(pady=(10, 2))
        self._compute_combo = self._create_combo(self._content, _COMPUTE_OPTIONS_DISPLAY, width=320)
        self._compute_combo.set(_COMPUTE_CFG_TO_DISPLAY.get(self._selected_compute, _COMPUTE_CFG_TO_DISPLAY["int8_float16"]))
        self._compute_combo.pack(pady=2)

    # ------------------------------------------------------------------
    # Step 4 — Install progress
    # ------------------------------------------------------------------

    def _build_step_install(self) -> None:
        self._create_label(self._content, "Instalando...", font_size=16, bold=True).pack(pady=10)

        self._progress = self._create_progress(self._content, width=400)
        self._progress.pack(pady=10)

        self._log_text = self._create_text(self._content, width=50, height=10)
        self._log_text.pack(pady=5)

        self._btn_next.configure(state="disabled")
        self._install_thread = threading.Thread(target=self._run_install, daemon=True)
        self._install_thread.start()

    def _log(self, msg: str) -> None:
        self._root.after(0, lambda: self._text_insert(self._log_text, msg))

    def _set_progress_safe(self, value: float) -> None:
        self._root.after(0, lambda: self._set_progress(self._progress, value))

    def _run_install(self) -> None:
        """Ejecuta la instalación en segundo plano."""
        try:
            self._set_progress_safe(0.1)
            self._log("Creando entorno virtual...")
            self._create_venv()

            self._set_progress_safe(0.3)
            self._log("Instalando PyTorch...")
            self._install_torch()

            self._set_progress_safe(0.6)
            self._log("Instalando dependencias...")
            self._install_requirements()

            self._set_progress_safe(0.8)
            self._log("Generando configuración...")
            self._write_config()

            self._set_progress_safe(0.9)
            self._log("Generando lanzador...")
            platform = get_platform()
            platform.generate_launcher()

            self._set_progress_safe(1.0)
            self._log("¡Instalación completada! Abriendo WhisperKey...")
            self._root.after(1500, self._auto_finish_and_launch)
        except Exception as exc:
            log.exception("Error durante la instalación")
            self._log(f"ERROR: {exc}")
            self._root.after(0, lambda: self._btn_next.configure(state="normal"))

    def _create_venv(self) -> None:
        project_root = pathlib.Path(__file__).parent.parent.resolve()
        venv_path = project_root / ".venv"
        if not venv_path.exists():
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    def _install_torch(self) -> None:
        platform = get_platform()
        device, _ = platform.detect_gpu()
        python = self._get_venv_python()

        if device == "cuda":
            cmd = [str(python), "-m", "pip", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu118"]
        elif device == "mps":
            cmd = [str(python), "-m", "pip", "install", "torch", "torchaudio"]
        else:
            cmd = [str(python), "-m", "pip", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cpu"]
        subprocess.run(cmd, check=True)

    def _install_requirements(self) -> None:
        python = self._get_venv_python()
        req_file = pathlib.Path(__file__).parent.parent / "requirements.txt"
        if req_file.exists():
            subprocess.run([str(python), "-m", "pip", "install", "-r", str(req_file)], check=True)

    def _write_config(self) -> None:
        config_dict = {
            "model": {
                "name": self._selected_model,
                "device": self._selected_device,
                "compute_type": self._selected_compute,
            },
            "app": {
                "first_run": False,
            },
        }
        config_path = pathlib.Path(__file__).parent.parent / "config.toml"
        config_module.write_config(str(config_path), config_dict)

    def _get_venv_python(self) -> pathlib.Path:
        platform = get_platform()
        return platform.get_venv_python()

    # ------------------------------------------------------------------
    # Step 5 — Done
    # ------------------------------------------------------------------

    def _build_step_done(self) -> None:
        self._create_label(self._content, "¡Instalación completada!", font_size=18, bold=True).pack(pady=20)
        self._create_label(
            self._content,
            "WhisperKey está listo para usar.\n"
            "Podés iniciarlo desde el lanzador generado.",
            font_size=13,
        ).pack(pady=10)

        self._launch_var = tk.IntVar(value=1)
        if ctk is not None:
            cb = ctk.CTkCheckBox(self._content, text="Lanzar WhisperKey ahora", variable=self._launch_var)
        else:
            cb = tk.Checkbutton(self._content, text="Lanzar WhisperKey ahora", variable=self._launch_var)
        cb.pack(pady=15)

        # Guardar referencia para usar al cerrar
        self._launch_checkbox = cb

        self._btn_next.configure(command=self._on_close_done)

    def _on_close_done(self) -> None:
        if getattr(self, "_launch_var", tk.IntVar(value=0)).get():
            self._launch_app()
        self._root.destroy()

    def _launch_app(self) -> None:
        platform = get_platform()
        python = platform.get_venv_python()
        project_root = platform.get_project_root()
        subprocess.Popen([str(python), "-m", "whisperkey"], cwd=str(project_root))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    InstallerWizard()


if __name__ == "__main__":
    main()
