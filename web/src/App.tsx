import React, { useState, useEffect, useCallback } from 'react';

import pildoraEscuchando from './assets/pill-escuchando.png';
import pildoraTranscribiendo from './assets/pill-transcribiendo.png';
import capturaAjustes from './assets/app-ajustes.png';
import capturaInicio from './assets/app-inicio.png';

const REPO = 'p5Patricio/WhisperKey';
const FALLBACK_VERSION = 'v1.4.3';
const FALLBACK_DOWNLOAD = `https://github.com/${REPO}/releases/latest/download/WhisperKey-Setup.exe`;

/* Marcas de 20px, trazo de 1.5. Sin emoji: rompen el registro tipográfico. */
const Glifo: React.FC<{ d: string }> = ({ d }) => (
  <svg
    className="tarjeta__marca"
    width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d={d} />
  </svg>
);

const GLIFOS = {
  rayo: 'M13 2 3 14h9l-1 8 10-12h-9l1-8Z',
  candado: 'M5 11h14v10H5V11Zm3 0V7a4 4 0 0 1 8 0v4',
  idioma: 'M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18ZM3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0Z',
  cursor: 'M4 4l7 16 2-7 7-2L4 4Z',
  capa: 'M4 8h16v9H4V8Zm4 13h8M12 17v4',
  memoria: 'M8 4h8v16H8V4ZM4 9h4M4 15h4M16 9h4M16 15h4',
  engranaje: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8-3-2 .6-.5 1.3 1 1.8-1.8 1.8-1.8-1-1.3.5L13 19h-2l-.6-2-1.3-.5-1.8 1L5.5 15.7l1-1.8-.5-1.3L4 12v-2l2-.6.5-1.3-1-1.8L7.3 4.5l1.8 1 1.3-.5L11 3h2l.6 2 1.3.5 1.8-1 1.8 1.8-1 1.8.5 1.3 2 .6v2Z',
  teclado: 'M3 7h18v10H3V7Zm3 3h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M8 14h8',
  cerebro: 'M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8V15a3 3 0 0 0 3 3h1V4H9Zm6 0a3 3 0 0 1 3 3 3 3 0 0 1 1 5.8V15a3 3 0 0 1-3 3h-1V4h0Z',
  arquitectura: 'M12 3 3 8l9 5 9-5-9-5ZM3 14l9 5 9-5M3 11l9 5 9-5',
  llave: 'M15 4a5 5 0 1 0-4.6 7L4 17.4V21h3.6l1.2-1.2v-2h2v-2h2l1.2-1.2A5 5 0 0 0 15 4Z',
  libro: 'M4 4h7a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4V4Zm16 0h-7a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h7V4Z',
};

const CARACTERISTICAS = [
  {
    glifo: GLIFOS.rayo,
    titulo: 'Motor C++ residente',
    texto: 'El modelo queda cargado en memoria. Cada dictado paga sólo la inferencia, no la carga desde disco.',
  },
  {
    glifo: GLIFOS.candado,
    titulo: 'Privado por construcción',
    texto: 'Tu voz no sale de tu computadora. Sin metadatos, sin llamadas a servidores remotos, sin cuentas.',
  },
  {
    glifo: GLIFOS.idioma,
    titulo: 'Spanglish técnico',
    texto: '«Hacé un pull request», «revisá el backend», «deploy en staging». Entiende cómo hablás de verdad.',
  },
  {
    glifo: GLIFOS.cursor,
    titulo: 'Inyección transparente',
    texto: 'El texto aparece en VS Code, Cursor, Slack u Obsidian. Tu portapapeles queda como estaba.',
  },
  {
    glifo: GLIFOS.capa,
    titulo: 'Indicador discreto',
    texto: 'Una píldora en la esquina te dice si está escuchando o transcribiendo. Nada más ocupa la pantalla.',
  },
  {
    glifo: GLIFOS.memoria,
    titulo: 'Control de la VRAM',
    texto: 'Liberá la memoria de la GPU desde la bandeja cuando necesites todo el equipo para otra cosa.',
  },
];

const COMPARATIVA = [
  ['Privacidad del audio', 'Todo en tu máquina', 'Enviado a servidores externos'],
  ['Costo', 'Gratis y de código abierto', 'USD 10 a 20 por mes'],
  ['Sin conexión', 'Funciona completo', 'Requiere internet siempre'],
  ['Spanglish técnico', 'Nativo, con contexto propio', 'Rígido o un solo idioma'],
  ['Auditoría', 'Código abierto, licencia MIT', 'Propietario y cerrado'],
];

const PASOS = [
  {
    numero: 'Paso 1',
    titulo: 'Descargá el instalador',
    texto: 'Un archivo de 28 MB. Sin cuentas, sin tarjetas, sin telemetría. Se instala sin permisos de administrador.',
    imagen: null as string | null,
    archivo: true,
  },
  {
    numero: 'Paso 2',
    titulo: 'El asistente hace el resto',
    texto: 'Detecta si tenés GPU NVIDIA o sólo CPU, prueba el micrófono y te deja capturar tus propias teclas. Termina en menos de un minuto.',
    imagen: capturaInicio,
  },
  {
    numero: 'Paso 3',
    titulo: 'Ajustá lo que quieras, cuando quieras',
    texto: 'Modelo, micrófono, teclas, indicador e historial. Todo desde la bandeja del sistema, sin tocar un archivo de configuración.',
    imagen: capturaAjustes,
  },
];

const PREGUNTAS = [
  {
    p: '¿Necesito una placa de video potente?',
    r: 'No. WhisperKey trae un motor optimizado para CPU con instrucciones AVX y AVX2. Si tenés una NVIDIA GTX o RTX, descarga sola el runtime CUDA y baja de 200 ms por dictado.',
  },
  {
    p: '¿Qué modelos de Whisper puedo usar?',
    r: 'Los cinco oficiales en formato GGML: tiny, base, small, medium y large-v3. Se cambian desde Configuración, sin reinstalar nada. Para Spanglish, small o superior.',
  },
  {
    p: '¿Puedo cambiar las teclas?',
    r: 'Sí. Push-to-Talk, Toggle y la de cancelar se reasignan desde Configuración, capturando en vivo la combinación que prefieras.',
  },
  {
    p: '¿Cómo se actualiza?',
    r: 'Sola. Cuando hay una versión nueva te avisa, verifica el instalador contra su hash y actualiza con un clic. Tus ajustes y modelos quedan donde están.',
  },
];

const DOCUMENTACION = [
  {
    glifo: GLIFOS.engranaje,
    titulo: 'Dónde vive tu configuración',
    texto: 'En %APPDATA%\\WhisperKey\\config.toml. Se crea solo, comentado, la primera vez que abrís la aplicación.',
  },
  {
    glifo: GLIFOS.teclado,
    titulo: 'Cambiar las teclas',
    texto: 'Bandeja del sistema → Configuración → Hotkeys. Capturá la combinación en vivo y guardá.',
  },
  {
    glifo: GLIFOS.cerebro,
    titulo: 'Elegir el modelo',
    texto: 'Cinco modelos GGML según tu equipo. «Automático» elige por vos mirando la memoria disponible.',
  },
  {
    glifo: GLIFOS.arquitectura,
    titulo: 'Cómo funciona por dentro',
    texto: 'Un whisper-server residente con un endpoint HTTP local. El audio se procesa ahí mismo y nunca sale a internet.',
  },
  {
    glifo: GLIFOS.llave,
    titulo: 'Si algo no anda',
    texto: '¿No graba? Esperá a que el ícono esté en verde. ¿No pega el texto? Probá en el Bloc de notas: algunas apps como administrador bloquean la simulación de teclado.',
  },
  {
    glifo: GLIFOS.libro,
    titulo: '¿Más detalle?',
    texto: 'El README en GitHub tiene la arquitectura completa, el troubleshooting extendido y cómo compilar desde el código.',
  },
];

const EJEMPLOS = [
  'Hacé un git push al branch de staging, deployá en Kubernetes y corré los tests de integración.',
  'Revisá el pull request de autenticación, agregá los logs en el backend y verificá el endpoint de Whisper.',
  'Creá una migración en PostgreSQL para los usuarios activos y optimizá las queries con un índice.',
];

export const App: React.FC = () => {
  const [version, setVersion] = useState(FALLBACK_VERSION);
  const [urlDescarga, setUrlDescarga] = useState(FALLBACK_DOWNLOAD);

  const [grabando, setGrabando] = useState(false);
  const [texto, setTexto] = useState(EJEMPLOS[0]);
  const [escribiendo, setEscribiendo] = useState(false);
  const [indice, setIndice] = useState(1);
  const [abierta, setAbierta] = useState<number | null>(0);

  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then((r) => r.json())
      .then((d) => {
        if (d.tag_name) setVersion(d.tag_name);
        const exe = d.assets?.find((a: { name?: string }) => a.name?.endsWith('.exe'));
        if (exe?.browser_download_url) setUrlDescarga(exe.browser_download_url);
      })
      .catch(() => {});
  }, []);

  const empezar = useCallback(() => {
    setGrabando((yaEstaba) => {
      if (yaEstaba) return yaEstaba;
      setTexto('');
      return true;
    });
  }, []);

  const terminar = useCallback(() => {
    setGrabando((yaEstaba) => {
      if (!yaEstaba) return yaEstaba;
      setEscribiendo(true);
      const objetivo = EJEMPLOS[indice % EJEMPLOS.length];
      setIndice((n) => n + 1);
      let i = 0;
      const t = setInterval(() => {
        i += 1;
        setTexto(objetivo.slice(0, i));
        if (i >= objetivo.length) {
          clearInterval(t);
          setEscribiendo(false);
        }
      }, 26);
      return false;
    });
  }, [indice]);

  useEffect(() => {
    const abajo = (e: KeyboardEvent) => {
      if (e.code === 'F9') { e.preventDefault(); empezar(); }
    };
    const arriba = (e: KeyboardEvent) => {
      if (e.code === 'F9') { e.preventDefault(); terminar(); }
    };
    window.addEventListener('keydown', abajo);
    window.addEventListener('keyup', arriba);
    return () => {
      window.removeEventListener('keydown', abajo);
      window.removeEventListener('keyup', arriba);
    };
  }, [empezar, terminar]);

  const estado = grabando ? 'Escuchando' : escribiendo ? 'Transcribiendo' : 'Listo';

  return (
    <>
      <header className="nav">
        <div className="nav__interior">
          <a href="#inicio" className="nav__marca">
            <img src="assets/logo.png" alt="" />
            <span>WhisperKey</span>
          </a>

          <nav aria-label="Secciones">
            <ul className="nav__enlaces">
              <li><a href="#dictado">Dictado</a></li>
              <li><a href="#caracteristicas">Características</a></li>
              <li><a href="#comparativa">Comparativa</a></li>
              <li><a href="#empezar">Empezar</a></li>
              <li><a href="#documentacion">Documentación</a></li>
              <li><a href="#preguntas">Preguntas</a></li>
            </ul>
          </nav>

          <div className="nav__acciones">
            <a
              href={`https://github.com/${REPO}`}
              target="_blank" rel="noopener noreferrer"
              className="nav__icono" aria-label="Repositorio en GitHub"
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
            </a>
            <a href={urlDescarga} className="btn btn--pill">Descargar</a>
          </div>
        </div>
      </header>

      <main id="inicio">
        {/* Héroe — lienzo blanco, el producto descansa al final de la teja */}
        <section className="teja teja--claro hero">
          <div className="contenido">
            <p className="eyebrow">{version} · Sin nube · Sin claves de API</p>
            <h1 className="display">
              <span>Dictado por voz local.</span>
              <span className="apagado">Cero nube, cero latencia.</span>
            </h1>
            <p className="lead">
              Convierte tu voz en texto donde ya estás escribiendo. Whisper corre en tu
              propia GPU o CPU, entiende el Spanglish técnico y pega el resultado en
              cualquier aplicación.
            </p>
            <div className="acciones">
              <a href={urlDescarga} className="btn btn--pill">Descargar para Windows</a>
              <a href={`https://github.com/${REPO}`} className="btn btn--texto"
                 target="_blank" rel="noopener noreferrer">Ver el código &rsaquo;</a>
            </div>
            <p className="hero__fino fino">
              <span>Instalador de 28 MB</span>
              <span>Windows 10 y 11 · 64 bits</span>
              <span>Licencia MIT</span>
            </p>
          </div>

          <div className="hero__producto">
            <img className="hero__pildora" src={pildoraEscuchando}
                 alt="Indicador de WhisperKey mostrando «Escuchando»" />
            <p className="fino hero__pie-producto">
              Esto es todo lo que aparece en pantalla mientras dictás.
            </p>
          </div>
        </section>

        {/* Teja oscura — la demo */}
        <section id="dictado" className="teja teja--oscuro">
          <div className="contenido">
            <div className="cabecera-seccion">
              <p className="eyebrow">Probalo acá mismo</p>
              <h2 className="display-lg">Mantené la tecla. Hablá. Soltá.</h2>
              <p className="lead">
                Así se siente dictar con WhisperKey. Mantené presionado el botón —
                o la tecla F9 de tu teclado— y soltá cuando termines.
              </p>
            </div>

            <div className="demo">
              <div className="demo__panel">
                <div className="demo__barra">
                  {grabando || escribiendo ? (
                    <img
                      className="demo__pildora"
                      src={grabando ? pildoraEscuchando : pildoraTranscribiendo}
                      alt={`Indicador de WhisperKey: ${estado}`}
                    />
                  ) : (
                    <>
                      <span className="demo__punto" />
                      <span>{estado} para dictar</span>
                    </>
                  )}
                </div>
                <div className="demo__salida" aria-live="polite">
                  {texto}
                  {(grabando || escribiendo) && <span className="demo__cursor" />}
                </div>
              </div>

              <div className="demo__control">
                <button
                  type="button"
                  className="btn btn--pill btn--pill-oscuro"
                  onMouseDown={empezar} onMouseUp={terminar} onMouseLeave={terminar}
                  onTouchStart={(e) => { e.preventDefault(); empezar(); }}
                  onTouchEnd={(e) => { e.preventDefault(); terminar(); }}
                >
                  {grabando ? 'Soltá para transcribir' : 'Mantené para dictar'}
                </button>
                <span className="tecla">F9</span>
              </div>
            </div>
          </div>
        </section>

        {/* Pergamino — las cifras, sin tarjetas */}
        <section className="teja teja--pergamino">
          <div className="contenido cifras">
            <div>
              <p className="cifra__valor">0</p>
              <p className="cifra__nota">bytes enviados a un servidor</p>
            </div>
            <div>
              <p className="cifra__valor">260 ms</p>
              <p className="cifra__nota">de latencia percibida por dictado</p>
            </div>
            <div>
              <p className="cifra__valor">$0</p>
              <p className="cifra__nota">sin suscripción ni límite de palabras</p>
            </div>
            <div>
              <p className="cifra__valor">MIT</p>
              <p className="cifra__nota">código abierto y auditable</p>
            </div>
          </div>
        </section>

        {/* Blanco — características */}
        <section id="caracteristicas" className="teja teja--claro">
          <div className="contenido--ancho">
            <div className="cabecera-seccion">
              <p className="eyebrow">Cómo está hecho</p>
              <h2 className="display-lg">Rápido porque no sale de tu máquina.</h2>
              <p className="lead">
                Un motor en C++ que se queda cargado, y un pipeline de audio que no
                pierde una sílaba.
              </p>
            </div>
            <div className="rejilla">
              {CARACTERISTICAS.map((c) => (
                <article className="tarjeta" key={c.titulo}>
                  <Glifo d={c.glifo} />
                  <h3>{c.titulo}</h3>
                  <p>{c.texto}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Teja oscura — comparativa */}
        <section id="comparativa" className="teja teja--oscuro">
          <div className="contenido">
            <div className="cabecera-seccion">
              <p className="eyebrow">Sin letra chica</p>
              <h2 className="display-lg">Local contra la nube.</h2>
            </div>
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Característica</th>
                  <th scope="col">WhisperKey</th>
                  <th scope="col">Servicios en la nube</th>
                </tr>
              </thead>
              <tbody>
                {COMPARATIVA.map(([que, nuestro, otros]) => (
                  <tr key={que}>
                    <td>{que}</td>
                    <td className="tabla__si"><span className="tabla__marca">✓</span>{nuestro}</td>
                    <td className="tabla__no">{otros}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Blanco — pasos con imagen de producto */}
        <section id="empezar" className="teja teja--claro">
          <div className="contenido">
            <div className="cabecera-seccion">
              <p className="eyebrow">Listo en un minuto</p>
              <h2 className="display-lg">Instalar y hablar.</h2>
            </div>

            {PASOS.map((p, i) => (
              <div className={`paso${i % 2 === 1 ? ' paso--invertido' : ''}`} key={p.titulo}>
                <div className="paso__texto">
                  <p className="paso__numero">{p.numero}</p>
                  <h3>{p.titulo}</h3>
                  <p>{p.texto}</p>
                  {i === 0 && (
                    <p style={{ marginTop: 'var(--e-md)' }}>
                      <a href={urlDescarga} className="btn btn--pill">Descargar ahora</a>
                    </p>
                  )}
                </div>
                {p.imagen ? (
                  <div className="paso__imagen">
                    <img src={p.imagen} alt={`WhisperKey — ${p.titulo}`} loading="lazy" />
                  </div>
                ) : (
                  <div className="paso__archivo">
                    <svg width="34" height="34" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"
                         strokeLinejoin="round" aria-hidden="true">
                      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
                      <path d="M14 3v5h5M12 12v5m0 0-2-2m2 2 2-2" />
                    </svg>
                    <div>
                      <strong>WhisperKey-Setup.exe</strong>
                      <span>28 MB · {version} · Windows 10 y 11</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Pergamino — documentación */}
        <section id="documentacion" className="teja teja--pergamino">
          <div className="contenido--ancho">
            <div className="cabecera-seccion">
              <p className="eyebrow">Documentación</p>
              <h2 className="display-lg">Todo lo que hace falta saber.</h2>
            </div>
            <div className="rejilla">
              {DOCUMENTACION.map((d) => (
                <article className="tarjeta" key={d.titulo}>
                  <Glifo d={d.glifo} />
                  <h3>{d.titulo}</h3>
                  <p>{d.texto}</p>
                </article>
              ))}
            </div>
            <p className="centrado" style={{ marginTop: 'var(--e-xl)' }}>
              <a href={`https://github.com/${REPO}#readme`} target="_blank" rel="noopener noreferrer">
                Leer el README completo &rsaquo;
              </a>
            </p>
          </div>
        </section>

        {/* Blanco — preguntas */}
        <section id="preguntas" className="teja teja--claro">
          <div className="contenido">
            <div className="cabecera-seccion">
              <p className="eyebrow">Preguntas</p>
              <h2 className="display-lg">Antes de descargar.</h2>
            </div>
            <div className="faq">
              {PREGUNTAS.map((q, i) => (
                <div className={`faq__item${abierta === i ? ' faq__item--abierto' : ''}`} key={q.p}>
                  <button
                    type="button"
                    className="faq__boton"
                    aria-expanded={abierta === i}
                    onClick={() => setAbierta(abierta === i ? null : i)}
                  >
                    {q.p}
                    <span className="faq__signo" aria-hidden="true">+</span>
                  </button>
                  <div className="faq__cuerpo">
                    <p>{q.r}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Teja oscura — cierre */}
        <section className="teja teja--oscuro cierre">
          <div className="contenido">
            <h2 className="display-lg">Escribí a la velocidad a la que hablás.</h2>
            <p className="lead">Gratis, sin registro, y tu voz no se va a ningún lado.</p>
            <div className="acciones" style={{ marginTop: 'var(--e-lg)' }}>
              <a href={urlDescarga} className="btn btn--pill btn--pill-oscuro">
                Descargar WhisperKey
              </a>
            </div>
            <p className="fino" style={{ marginTop: 'var(--e-md)', color: 'var(--sobre-oscuro-suave)' }}>
              {version} · Windows 10 y 11 · 28 MB
            </p>
          </div>
        </section>
      </main>

      <footer className="pie">
        <div className="pie__interior">
          <ul className="pie__enlaces">
            <li><a href={`https://github.com/${REPO}`} target="_blank" rel="noopener noreferrer">Repositorio</a></li>
            <li><a href={`https://github.com/${REPO}/releases`} target="_blank" rel="noopener noreferrer">Versiones</a></li>
            <li><a href={`https://github.com/${REPO}/blob/main/CHANGELOG.md`} target="_blank" rel="noopener noreferrer">Novedades</a></li>
            <li><a href={`https://github.com/${REPO}#readme`} target="_blank" rel="noopener noreferrer">Documentación</a></li>
            <li><a href={`https://github.com/${REPO}/issues`} target="_blank" rel="noopener noreferrer">Reportar un problema</a></li>
            <li><a href={`https://github.com/${REPO}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer">Licencia MIT</a></li>
          </ul>
          <p style={{ margin: 0 }}>
            WhisperKey © 2026 · Creado por p5Patricio · El audio nunca sale de tu equipo.
          </p>
        </div>
      </footer>
    </>
  );
};

export default App;
