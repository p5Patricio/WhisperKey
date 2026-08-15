# WhisperKey — Agent Guidelines & Project Architecture

Este documento define la arquitectura, normas y directrices operativas que **todo agente de IA** debe leer y respetar antes de interactuar o modificar este repositorio.

---

## 1. Reglas Generales y Package Managers

- **Gestor de Paquetes Web (ESTRICTO):** Para cualquier desarrollo frontend, web o herramientas de Node.js/TypeScript, **SOLO USAR PNPM (`pnpm`)**. Queda terminantemente prohibido el uso de `npm` o `yarn`.
- **Commits y Git:**
  - Usar **Conventional Commits** exclusivamente (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`).
  - **NUNCA** agregar atribuciones de IA como `Co-Authored-By: ...` o firmas automáticas en los commits.
- **Skills del Proyecto:**
  - Se gestionan mediante `npx autoskills`. Las skills activas residen en `.agents/skills/` y se bloquean en `skills-lock.json`.
- **Suite de Pruebas (Python):**
  - Se ejecutan con `.venv\Scripts\pytest tests/` (o `pytest tests/`).
  - Todo cambio en el código fuente debe mantener el 100% de los tests pasando sin regresiones (216+ tests).

---

## 2. Visión General del Proyecto y Arquitectura

**WhisperKey** es una herramienta de escritorio multiplataforma (Windows / Linux / macOS) para dictado por voz 100% local, offline y bilingüe (español/inglés con optimización para Spanglish técnico), construida sobre OpenAI Whisper y `whisper.cpp`.

### Componentes Clave:

1. **Motor C++ Residente (`whisperkey/engine.py`):**
   - No carga el modelo en cada pulsación. Mantiene un subproceso local `whisper-server.exe` escuchando en loopback (`127.0.0.1`) en un puerto efímero asignado dinámicamente.
   - En Windows, el subproceso está asignado a un **Win32 Job Object** con `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` para garantizar que si el proceso padre finaliza o crashea, el kernel de Windows mata inmediatamente a `whisper-server.exe` liberando RAM/VRAM.
2. **Captura y Streaming de Audio (`whisperkey/audio.py`):**
   - Utiliza `sounddevice` (PortAudio) con callback no bloqueante `O(1)` y cola acotada (`drop-oldest`).
   - Detección de silencios por RMS (`_SILENCE_RMS_THRESHOLD`) y corte de seguridad para grabaciones continuas prolongadas (`max_duration`).
3. **Escucha Global de Teclado (`whisperkey/hotkeys.py`):**
   - Listener de bajo nivel con `pynput` para Push-to-Talk (`F9`), Toggle (`F10`) y carga/descarga manual de modelo en caliente.
4. **Inyección de Texto (`whisperkey/injection.py`):**
   - Simula atajo nativo (`Ctrl+V` en Windows/Linux, `Cmd+V` en macOS) vía portapapeles con guardado y restauración segura del contenido previo.
5. **Capa de Abstracción de Plataforma (`whisperkey/platform/`):**
   - `BasePlatform`, `WindowsPlatform`, `LinuxPlatform`, `MacPlatform`.
   - Implementa **Single Instance Mutex** (`CreateMutexW` con prefijo `Local\`) para evitar ejecución concurrente de múltiples instancias.
6. **Configuración y Migración (`whisperkey/config.py`):**
   - Archivo `config.toml` almacenado canónicamente en `%APPDATA%/WhisperKey/config.toml` (modo compilado) o en la raíz del proyecto (desarrollo).
   - Fusionado profundo (`_deep_merge`) para preservar secciones completas (`[transcription]`, `[app]`, `[overlay]`).
7. **Actualizaciones Automáticas (`whisperkey/updater.py`):**
   - Consulta `https://api.github.com/repos/p5Patricio/WhisperKey/releases/latest`.
   - Soporta descarga e instalación silenciosa automática (`WhisperKey-Setup.exe /SILENT /CLOSEAPPLICATIONS`) con verificación de hash SHA256 y fallback a descarga manual.

---

## 3. Estructura de Directorios

```
WhisperKey/
├── .agents/               # Skills del agente instaladas via autoskills
├── assets/                # Logos, iconos (.ico, .icns, .png) y binarios empaquetados
├── docs/                  # Landing page pública desplegada en GitHub Pages
├── installer/             # Scripts de compilación de Inno Setup (whisperkey.iss, build.bat)
├── tests/                 # Suite completa de tests unitarios e integración (pytest)
├── tools/                 # Scripts de utilidad (tools/build.py para PyInstaller)
├── web/                   # Aplicación web / Landing page (gestionada con PNPM)
├── whisperkey/            # Código fuente principal de la aplicación en Python
├── WhisperKey.spec        # Especificación de PyInstaller
├── pyproject.toml         # Configuración del entorno y herramientas
├── requirements.txt       # Dependencias de Python
└── AGENTS.md              # Este archivo de directrices
```

---

## 4. Distribución y Empaquetado

- **PyInstaller:** `python tools/build.py` empaqueta el runtime de Python y el motor ligero de CPU en `dist/WhisperKey/`.
- **Instalador Inno Setup:** `installer/build.bat` compila `dist/WhisperKey-Setup.exe` (~28 MB) con desinstalador nativo en Windows y soporte para inicio automático.
- **GitHub Pages:** La web en `docs/` se despliega automáticamente desde la rama `main` en `https://p5patricio.github.io/WhisperKey/`.
