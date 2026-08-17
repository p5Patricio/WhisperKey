import React, { useState, useEffect } from 'react';
import Threads from './components/Threads/Threads';

const REPO = 'p5Patricio/WhisperKey';
const FALLBACK_VERSION = 'v1.2.0';
const FALLBACK_DOWNLOAD = `https://github.com/${REPO}/releases/latest/download/WhisperKey-Setup.exe`;

export const App: React.FC = () => {
  const [version, setVersion] = useState(FALLBACK_VERSION);
  const [downloadUrl, setDownloadUrl] = useState(FALLBACK_DOWNLOAD);
  
  // Interactive Demo State
  const [isRecording, setIsRecording] = useState(false);
  const [displayText, setDisplayText] = useState('Hacé un git push al branch de staging y deployá los cambios en Kubernetes.');
  const [demoStatus, setDemoStatus] = useState('Listo para dictar');
  const [sampleIdx, setSampleIdx] = useState(0);
  
  // FAQ state
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const sampleTexts = [
    'Hacé un git push al branch de staging, deployá en Kubernetes y corré los tests de integración.',
    'Revisá el pull request de autenticación, agregá los logs en el backend y verificá el endpoint de Whisper.',
    'Creá una nueva migración en PostgreSQL para los usuarios activos y optimizá las queries con un índice.'
  ];

  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then(res => res.json())
      .then(data => {
        if (data.tag_name) setVersion(data.tag_name);
        const exeAsset = data.assets?.find((a: any) => a.name?.endsWith('.exe'));
        if (exeAsset?.browser_download_url) {
          setDownloadUrl(exeAsset.browser_download_url);
        }
      })
      .catch(() => {});
  }, []);

  const handleStartRecording = () => {
    if (isRecording) return;
    setIsRecording(true);
    setDemoStatus('● Grabando voz');
  };

  const handleStopRecording = () => {
    if (!isRecording) return;
    setIsRecording(false);
    setDemoStatus('✓ Transcrito');

    const nextText = sampleTexts[sampleIdx % sampleTexts.length];
    setSampleIdx(prev => prev + 1);
    
    setDisplayText('');
    let charIdx = 0;
    const interval = setInterval(() => {
      if (charIdx < nextText.length) {
        setDisplayText(nextText.slice(0, charIdx + 1));
        charIdx++;
      } else {
        clearInterval(interval);
      }
    }, 28);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'F9' || e.code === 'F9') {
        e.preventDefault();
        handleStartRecording();
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'F9' || e.code === 'F9') {
        e.preventDefault();
        handleStopRecording();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [isRecording, sampleIdx]);

  return (
    <div className="app-root">
      {/* Fixed Fullscreen Background */}
      <Threads
        className="threads-fixed-bg"
        color={[0.15, 0.55, 1.0]}
        amplitude={1.8}
        distance={0.15}
        enableMouseInteraction={false}
      />

      {/* Header */}
      <header className="site-header">
        <div className="container nav-container">
          <a href="#" className="brand-logo">
            <img src="assets/logo.png" alt="WhisperKey Logo" />
            <span>WhisperKey</span>
          </a>

          <nav>
            <ul className="nav-links">
              <li><a href="#features" className="nav-link">Características</a></li>
              <li><a href="#demo" className="nav-link">Demo</a></li>
              <li><a href="#comparativa" className="nav-link">Comparativa</a></li>
              <li><a href="#como-empezar" className="nav-link">Cómo Empezar</a></li>
              <li><a href="#documentacion" className="nav-link">Documentación</a></li>
              <li><a href="#faq" className="nav-link">Preguntas Frecuentes</a></li>
            </ul>
          </nav>

          <div className="nav-actions">
            <a href={`https://github.com/${REPO}`} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
              GitHub
            </a>
            <a href={downloadUrl} className="btn btn-primary btn-sm">
              Descargar .exe
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="container hero-content">
          <div className="badge">
            <span className="badge-dot"></span>
            <span>Versión <strong>{version}</strong> • 100% Offline • Sin API Keys</span>
          </div>


          <h1 className="hero-title">
            Dictado por voz local.<br />
            <span className="gradient-text">Cero nube, cero latencia.</span>
          </h1>

          <p className="hero-subtitle">
            Convierte tu voz en texto en tiempo real con <strong>OpenAI Whisper</strong> corriendo directamente en tu GPU o CPU. Soporte nativo para <em>Spanglish técnico</em> e inyección instantánea en cualquier editor o aplicación.
          </p>

          <div className="hero-cta">
            <a href={downloadUrl} className="btn btn-primary btn-lg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Descargar para Windows (.exe)
            </a>
            <a href={`https://github.com/${REPO}`} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-lg">
              Ver Código Abierto
            </a>
          </div>

          <div className="hero-meta">
            <span>✓ Instalador portable (~28 MB)</span>
            <span>✓ Windows 10/11 x64</span>
            <span>✓ Licencia MIT</span>
          </div>
        </div>
      </section>

      {/* Interactive Demo */}
      <section id="demo" className="section" style={{ paddingTop: 0 }}>
        <div className="container">
          <div className="showcase-container">
            <div className="window-header">
              <div className="window-dots">
                <span className="dot dot-red"></span>
                <span className="dot dot-yellow"></span>
                <span className="dot dot-green"></span>
              </div>
              <div className="window-title">WhisperKey Interactive Simulator — main.py</div>
              <div className="window-status">
                {isRecording && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                    <span style={{ width: '3px', height: '12px', background: '#38bdf8', borderRadius: '2px', animation: 'pulse 0.6s infinite alternate' }}></span>
                    <span style={{ width: '3px', height: '18px', background: '#38bdf8', borderRadius: '2px', animation: 'pulse 0.4s infinite alternate 0.2s' }}></span>
                    <span style={{ width: '3px', height: '10px', background: '#38bdf8', borderRadius: '2px', animation: 'pulse 0.8s infinite alternate 0.4s' }}></span>
                  </span>
                )}
                <span>{demoStatus}</span>
              </div>
            </div>

            <div className="interactive-demo-body">
              <div className="demo-controls">
                <h3 className="demo-title">Probá el dictado en vivo</h3>
                <p className="demo-desc">
                  Hacé clic y mantené presionado el botón (o presioná <span className="key-badge">F9</span> en tu teclado) para simular una grabación por Push-to-Talk.
                </p>

                <button
                  className={`hotkey-trigger-btn ${isRecording ? 'active' : ''}`}
                  onMouseDown={handleStartRecording}
                  onMouseUp={handleStopRecording}
                  onTouchStart={(e) => { e.preventDefault(); handleStartRecording(); }}
                  onTouchEnd={(e) => { e.preventDefault(); handleStopRecording(); }}
                  type="button"
                >
                  <span className="btn-label">{isRecording ? 'Escuchando...' : 'Presionar F9 para dictar'}</span>
                  <span className="key-badge">F9 / PTT</span>
                </button>
              </div>

              <div className="demo-editor">
                <div className="editor-header">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                  <span>Terminal / Editor de código</span>
                </div>
                <div className="editor-output">
                  <span style={{ color: '#64748b' }}>// El texto dictado se inyecta automáticamente aquí...</span><br /><br />
                  <span style={{ color: '#38bdf8' }}>$ </span><span>{displayText}</span><span className="cursor-blink"></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Metrics */}
      <section className="metrics-section">
        <div className="container">
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-value">0 ms</div>
              <div className="metric-label">Datos enviados a servidores (100% en tu máquina)</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">&lt;300ms</div>
              <div className="metric-label">Latencia con motor residente C++ (whisper.cpp)</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">$0.00</div>
              <div className="metric-label">Sin suscripciones, sin límites de palabras</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">100%</div>
              <div className="metric-label">Código abierto bajo licencia libre MIT</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="section">
        <div className="container">
          <div className="section-header">
            <div className="section-tag">Diseñado para Máximo Rendimiento</div>
            <h2 className="section-title">El dictado profesional que respeta tu privacidad</h2>
            <p className="section-subtitle">
              Construido desde cero con un motor en C++ de ultra baja latencia y optimizaciones de hardware de última generación.
            </p>
          </div>

          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">⚡</div>
              <h3 className="feature-title">Motor C++ Residente</h3>
              <p className="feature-desc">
                Mantiene el modelo cargado en memoria local sin recargar desde disco en cada dictado. Solo pagás el costo de inferencia.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🔒</div>
              <h3 className="feature-title">100% Privado y Offline</h3>
              <p className="feature-desc">
                Tu voz nunca sale de tu computadora. Cero metadatos, cero conexiones a servidores remotos, ideal para código y datos confidenciales.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🌐</div>
              <h3 className="feature-title">Spanglish Técnico Nativo</h3>
              <p className="feature-desc">
                Entiende perfectamente mezclas bilingües de programadores: <em>"hacé un pull request"</em>, <em>"revisá el backend"</em> o <em>"deploy en staging"</em> sin errores.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🎯</div>
              <h3 className="feature-title">Inyección Transparente</h3>
              <p className="feature-desc">
                Pega el texto directamente en VS Code, Cursor, Discord, Slack, Obsidian o cualquier ventana activa preservando tu portapapeles.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🎮</div>
              <h3 className="feature-title">Overlay Visual HUD</h3>
              <p className="feature-desc">
                Indicador discreto en pantalla que te avisa cuándo está escuchando o procesando sin quitar el foco de tus juegos o herramientas.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🚀</div>
              <h3 className="feature-title">Control de VRAM Inteligente</h3>
              <p className="feature-desc">
                Descargá el modelo de la memoria GPU con un solo clic desde la bandeja del sistema cuando necesites todo el rendimiento para renderizar o jugar.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Comparison */}
      <section id="comparativa" className="section" style={{ background: 'rgba(10, 14, 22, 0.4)' }}>
        <div className="container">
          <div className="section-header">
            <div className="section-tag">Transparencia Total</div>
            <h2 className="section-title">WhisperKey vs Servicios en la Nube</h2>
            <p className="section-subtitle">Por qué ejecutar IA localmente supera a cualquier solución SaaS tradicional.</p>
          </div>

          <div className="comparison-container">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Característica</th>
                  <th style={{ color: 'var(--accent-primary-hover)' }}>WhisperKey</th>
                  <th style={{ color: 'var(--text-muted)' }}>Servicios SaaS / Cloud</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Privacidad de Audio</strong></td>
                  <td><span className="check-mark">✓ 100% Local (Tu máquina)</span></td>
                  <td><span className="cross-mark">✗ Enviado a servidores externos</span></td>
                </tr>
                <tr>
                  <td><strong>Costo / Suscripción</strong></td>
                  <td><span className="check-mark">✓ Gratis y Open Source</span></td>
                  <td><span className="cross-mark">✗ $10 - $20 USD / mes</span></td>
                </tr>
                <tr>
                  <td><strong>Funciona sin Internet</strong></td>
                  <td><span className="check-mark">✓ Sí, totalmente offline</span></td>
                  <td><span className="cross-mark">✗ Requiere conexión constante</span></td>
                </tr>
                <tr>
                  <td><strong>Spanglish para Desarrolladores</strong></td>
                  <td><span className="check-mark">✓ Optimizado con Whisper</span></td>
                  <td><span className="cross-mark">✗ Rígido / Solo un idioma</span></td>
                </tr>
                <tr>
                  <td><strong>Auditoría del Código</strong></td>
                  <td><span className="check-mark">✓ Código abierto (MIT)</span></td>
                  <td><span className="cross-mark">✗ Propietario / Código cerrado</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Steps */}
      <section id="como-empezar" className="section">
        <div className="container">
          <div className="section-header">
            <div className="section-tag">Listo en 60 Segundos</div>
            <h2 className="section-title">¿Cómo empezar a usarlo?</h2>
            <p className="section-subtitle">Sin configuraciones complejas ni terminales.</p>
          </div>

          <div className="steps-grid">
            <div className="step-card">
              <div className="step-number">1</div>
              <h3 className="step-title">Descargá el instalador</h3>
              <p className="step-desc">Hacé clic en "Descargar .exe" arriba o buscá el último release en GitHub. Bajás <code style={{ color: 'var(--accent-cyan)' }}>WhisperKey-Setup.exe</code> (~28 MB) — sin cuentas, sin tarjetas.</p>
            </div>

            <div className="step-card">
              <div className="step-number">2</div>
              <h3 className="step-title">Seguí el Onboarding</h3>
              <p className="step-desc">Al abrir WhisperKey por primera vez, un asistente detecta tu hardware (GPU NVIDIA o CPU), prueba tu micrófono en segundos y te deja capturar tus propios hotkeys.</p>
            </div>

            <div className="step-card">
              <div className="step-number">3</div>
              <h3 className="step-title">Elegí tu modo: F9 o F10</h3>
              <p className="step-desc">Mantené presionado <code style={{ color: 'var(--accent-cyan)' }}>F9</code> para dictar mientras hablás (Push-to-Talk), o presioná <code style={{ color: 'var(--accent-cyan)' }}>F10</code> una vez para activar el modo Toggle y volvé a presionarlo para terminar.</p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="section" style={{ background: 'rgba(10, 14, 22, 0.4)' }}>
        <div className="container">
          <div className="section-header">
            <div className="section-tag">Resolvé tus Dudas</div>
            <h2 className="section-title">Preguntas Frecuentes</h2>
          </div>

          <div className="faq-container">
            {[
              {
                q: "¿Necesito una tarjeta gráfica potente para usarlo?",
                a: "No es obligatorio. WhisperKey incluye un motor de inferencia optimizado para CPU con instrucciones SIMD (AVX/AVX2). Si tenés una GPU NVIDIA (GTX/RTX), la app descargará automáticamente el runtime CUDA para lograr latencias inferiores a 200 ms."
              },
              {
                q: "¿Qué modelos de Whisper están soportados?",
                a: "Soporta todos los modelos GGML oficiales: tiny, base, small, medium y large-v3. Podés cambiar el modelo en cualquier momento desde la ventana de Configuración."
              },
              {
                q: "¿Puedo cambiar las teclas de acceso rápido (hotkeys)?",
                a: "Sí. Desde el menú de Configuración podés reasignar tanto la tecla de Push-to-Talk (por defecto F9 o Caps Lock) como la de modo Toggle (por defecto F10)."
              },
              {
                q: "¿Cómo se actualiza la aplicación?",
                a: "WhisperKey incluye un actualizador automático integrado. Cuando haya una nueva versión disponible en GitHub, te mostrará un aviso y podrás actualizar con un solo clic sin perder tus configuraciones ni modelos."
              }
            ].map((item, idx) => (
              <div key={idx} className={`faq-item ${openFaq === idx ? 'open' : ''}`}>
                <button className="faq-question" onClick={() => setOpenFaq(openFaq === idx ? null : idx)}>
                  <span>{item.q}</span>
                  <span className="faq-icon">+</span>
                </button>
                <div className="faq-answer">
                  <p>{item.a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Documentation */}
      <section id="documentacion" className="section">
        <div className="container">
          <div className="section-header">
            <div className="section-tag">Soporte y Configuración</div>
            <h2 className="section-title">Documentación</h2>
            <p className="section-subtitle">
              Todo lo que necesitás para configurar, personalizar y resolver problemas — sin salir de la página.
            </p>
          </div>

          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">⚙️</div>
              <h3 className="feature-title">Dónde vive tu configuración</h3>
              <p className="feature-desc">
                Todos tus ajustes se guardan en <code style={{ color: 'var(--accent-cyan)' }}>%APPDATA%\WhisperKey\config.toml</code>. Se crea solo, con valores por defecto, la primera vez que abrís la app.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">⌨️</div>
              <h3 className="feature-title">Cambiar tus hotkeys</h3>
              <p className="feature-desc">
                Clic derecho en el ícono de la bandeja → Configuración → pestaña Hotkeys. Capturá en vivo la combinación que quieras para Push-to-Talk, Toggle o Cargar modelo.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🧠</div>
              <h3 className="feature-title">Elegí tu modelo Whisper</h3>
              <p className="feature-desc">
                Desde <em>tiny</em> hasta <em>large-v3</em>, cinco modelos GGML para elegir según tu hardware. Cambialo cuando quieras desde Configuración → Modelo, sin reinstalar nada.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🏗️</div>
              <h3 className="feature-title">Cómo funciona por dentro</h3>
              <p className="feature-desc">
                WhisperKey mantiene un servidor <code style={{ color: 'var(--accent-cyan)' }}>whisper-server.exe</code> residente en tu máquina, con un endpoint HTTP local para transcribir sin recargar el modelo en cada dictado. Tu audio se procesa ahí mismo — nunca sale a internet.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">🛠️</div>
              <h3 className="feature-title">Troubleshooting rápido</h3>
              <p className="feature-desc">
                ¿No graba? Esperá a que el ícono de bandeja esté verde. ¿No inyecta texto? Probá primero en el Bloc de notas — algunas apps con permisos de administrador bloquean la simulación de teclado.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">📖</div>
              <h3 className="feature-title">¿Necesitás más detalle?</h3>
              <p className="feature-desc">
                Esta página cubre lo esencial. El README en GitHub tiene la arquitectura completa, troubleshooting extendido y la guía para compilar desde código fuente.{' '}
                <a href={`https://github.com/${REPO}#readme`} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)' }}>
                  Ver README completo →
                </a>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Final */}
      <section id="descargar" className="section">
        <div className="container">
          <div className="cta-box">
            <h2 className="cta-title">Empezá a escribir a la velocidad de tu voz</h2>
            <p className="cta-desc">
              Descargá WhisperKey gratis, sin registros y con total control de tu privacidad.
            </p>
            <a href={downloadUrl} className="btn btn-primary btn-lg">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Descargar WhisperKey para Windows
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="site-footer">
        <div className="container footer-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <img src="assets/logo.png" alt="Logo" style={{ width: '22px', height: '22px', borderRadius: '4px' }} />
            <span>WhisperKey © 2026 • Creado por <strong>p5Patricio</strong></span>
          </div>

          <div className="footer-links">
            <a href={`https://github.com/${REPO}`} target="_blank" rel="noopener noreferrer">Repositorio en GitHub</a>
            <a href={`https://github.com/${REPO}/releases`} target="_blank" rel="noopener noreferrer">Releases</a>
            <a href={`https://github.com/${REPO}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer">Licencia MIT</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
