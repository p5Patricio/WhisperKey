# WhisperKey — Marketing Copy

> Documento de copy para releases, redes sociales y comunicaciones del proyecto.

---

## 1. Tagline / Headline principal

**"Dictado por voz local, sin nube, bilingüe español/inglés."**

Variantes:
- *"Hablá, transcribí, pegá. Todo en tu máquina."*
- *"Whisper corriendo en tu máquina, sin enviar nada a internet."*
- *"El dictado profesional que no te espía."*

---

## 2. Elevator Pitch (30 segundos)

WhisperKey es una aplicación de escritorio que convierte tu voz en texto en tiempo real usando modelos de IA locales (OpenAI Whisper). Funciona 100% offline: tu voz nunca sale de tu computadora. Soporta Spanglish técnico, se integra con cualquier aplicación vía clipboard, y gestiona tu VRAM inteligentemente para que puedas usarla mientras jugás o trabajás con gráficos pesados.

---

## 3. Value Propositions

### Para desarrolladores y profesionales técnicos
- **100% offline** — cero dependencia de internet, cero filtración de datos sensibles
- **Spanglish nativo** — el modelo large-v3 entiende "hacé un `git push` al `branch` de `staging`" sin drama
- **Inyección automática** — el texto aparece donde estés escribiendo, sin copiar y pegar
- **Gestión de VRAM** — cargá/descargá el modelo desde la bandeja del sistema al toque

### Para usuarios de privacidad
- **Nada sale de tu máquina** — ni metadatos, ni audio, ni texto
- **Sin cuentas, sin API keys, sin suscripciones** — lo descargás y funciona para siempre
- **Código abierto (MIT)** — podés auditar cada línea que corre

### Para gamers y creadores de contenido
- **Overlay visual** — sabés si está grabando, cargando, o en error sin salir del juego
- **Hotkeys configurables** — Push-to-Talk (F9) o Toggle (F10), a tu gusto
- **Liberación de VRAM** — descargá el modelo cuando necesitás todo el GPU para renderizar

---

## 4. GitHub Release Notes (v1.2.0)

### What's New

**GUI Installer + Branding Profesional**

Esta release transforma WhisperKey de un script de Python a una aplicación de escritorio completa:

- 🎨 **Instalador profesional (Inno Setup)** — `installer\build.bat` corre PyInstaller + Inno Setup y genera `WhisperKey-Setup.exe`, con auto-update silencioso incorporado
- 🚀 **Onboarding interactivo** — primer uso guiado con test de micrófono, captura de hotkeys en vivo, y tutorial rápido
- ⚙️ **Configuración visual** — ventana con tabs para modelo, audio, hotkeys y overlay
- 💫 **Splash screen** — feedback visual durante la carga del modelo Whisper
- 🔔 **Bandeja del sistema mejorada** — íconos reales con estados coloridos (idle, loading, ready, error)
- 🔄 **Auto-updater** — verifica automáticamente si hay nuevas versiones en GitHub Releases
- ⚡ **Motor C++ nativo (whisper.cpp/GGML)** — motor CPU incluido en el instalador (~8 MB) que funciona out-of-the-box; el motor CUDA se descarga automáticamente on-demand para usuarios con GPU NVIDIA; `whisper-server.exe` corre como servidor HTTP local residente para transcripciones repetidas de baja latencia
- 🎯 **Branding completo** — íconos .ico (Windows), .icns (macOS), .png (Linux) generados programáticamente

**Cross-platform (Windows / Linux / macOS)**

- Abstracción de plataforma completa en `whisperkey/platform/`
- Atajos de pegado adaptativos (Ctrl+V / Cmd+V)
- Beep nativo según SO
- Lanzadores nativos (.vbs, .sh, .app)
- Inicio automático (Startup folder, systemd, LaunchAgent)

**Robustez y thread-safety**

- AppState protegido con locks — cero race conditions
- Graceful shutdown — todos los threads se unen ordenadamente
- Cola de audio acotada (`maxsize=100`) con drop-oldest
- Clipboard protegido — contenido previo se guarda y restaura
- VAD integrado — elimina transcripciones de silencio y ruido
- Detección automática de hardware — sugiere el modelo óptimo
- Errores estructurados con mensajes en español entendibles

### Assets

- Source code (zip)
- Source code (tar.gz)

### Install from source

**Para usuarios finales**: descargá `WhisperKey-Setup.exe` desde la [página de Releases](https://github.com/p5Patricio/WhisperKey/releases).

**Para desarrolladores**:

```bash
git clone https://github.com/p5Patricio/WhisperKey.git
cd WhisperKey
installer\build.bat
```

---

## 5. Twitter / X Thread

**Tweet 1 (hook):**
> Estoy cansado de que cada app de dictado me pida "conectá tu cuenta" y mande mi voz a quién sabe dónde.
>
> Así que construí WhisperKey: dictado por voz 100% offline, con Whisper corriendo en TU máquina.
>
> Open source. Sin suscripción. Sin nube. 🧵

**Tweet 2 (demo):**
> Apretás F9, hablás, soltás.
>
> El texto aparece donde estés escribiendo. Notion, VS Code, WhatsApp Web, el juego que sea.
>
> No copiar y pegar. No pestañeo de ventanas. Aparece.

**Tweet 3 (tech):**
> Soporta Spanglish técnico nativo.
>
> "Hacé un git push al branch de staging, pero primero corré los tests de pytest."
>
> Lo entiende. Sin configurar idioma. Sin traducir.

**Tweet 4 (privacidad):**
> Tu voz NUNCA sale de tu máquina.
>
> Ni metadatos, ni audio, ni texto. Nada.
>
> Código abierto (MIT). Podés auditar cada línea.

**Tweet 5 (gaming):**
> Y si necesitás VRAM para renderizar o jugar:
>
> Clic derecho en la bandeja → "Descargar modelo". VRAM liberada al instante.
>
> Cuando terminás: "Cargar modelo". Listo en 10 segundos.

**Tweet 6 (CTA):**
> WhisperKey v1.2.0 ya está disponible.
>
> GUI installer, onboarding wizard, settings visual, auto-updater, branding profesional.
>
> 👉 github.com/p5Patricio/WhisperKey
>
> ⭐ Si te sirve, una estrella ayuda un montón.

---

## 6. LinkedIn Post

> **Lancé WhisperKey v1.2.0 — Dictado por voz 100% offline con Whisper**
>
> Durante los últimos meses transformé un script de Python de una sola noche en una aplicación de escritorio profesional, cross-platform, con GUI completa.
>
> **¿Qué resuelve?**
> Las herramientas de dictado existentes o mandan tu voz a la nube (privacidad cero) o no entienden Spanglish técnico. WhisperKey corre Whisper localmente en tu equipo, transcribe en tiempo real, e inyecta el texto donde estés escribiendo.
>
> **Lo nuevo en v1.2.0:**
> • Instalador profesional (Inno Setup), con onboarding que detecta tu hardware automáticamente
> • Wizard de primer uso con test de micrófono y captura de hotkeys
> • Configuración visual con pestañas
> • Splash screen durante carga del modelo
> • Auto-updater desde GitHub Releases
> • Iconos y branding profesionales
>
> **Stack:** Python 3.12, whisper.cpp (motor C++/GGML), customtkinter, pystray, pynput.
>
> Es 100% open source (MIT). Si te interesa la intersección de IA local, privacidad y UX de escritorio, pasá a ver el repo.
>
> 👉 github.com/p5Patricio/WhisperKey
>
> #OpenSource #MachineLearning #Python #Whisper #VoiceToText #PrivacyFirst #LocalAI

---

## 7. Product Hunt (futuro)

**Name:** WhisperKey

**Tagline:** Dictado por voz local con Whisper. Sin nube. Sin suscripción. Spanglish nativo.

**Description:**
WhisperKey convierte tu voz en texto en tiempo real usando OpenAI Whisper corriendo 100% en tu máquina. Sin enviar audio a ningún servidor. Sin suscripciones. Sin cuentas.

Soporta Spanglish técnico sin configurar idioma. Inyecta el texto automáticamente donde estés escribiendo. Gestiona tu VRAM para que puedas usarla mientras jugás o trabajás.

Con GUI installer, onboarding wizard, settings visual, splash screen, auto-updater, e iconos profesionales.

**Topics:** Productivity, Developer Tools, Open Source, AI, Privacy

---

## 8. One-liner para la bio / descripción corta

> WhisperKey — Dictado por voz local con Whisper. Sin nube. Spanglish nativo. 100% privado. 🎙️➡️⌨️
