/**
 * WhisperKey Landing Page Interactive Logic
 */
import { initThreads } from './threads.js';

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize WebGL Threads background
  const threadsContainer = document.getElementById('threads-canvas-container');
  if (threadsContainer) {
    initThreads(threadsContainer, {
      color: [0.25, 0.85, 0.75], // Teal / emerald tech glow
      amplitude: 2.4,
      distance: 0,
      enableMouseInteraction: true,
    });
  }

  // 2. Fetch Latest Release Info from GitHub
  fetchGitHubRelease();

  // 3. Interactive Dictation Simulator
  initDictationSimulator();

  // 4. FAQ Accordion
  initFaqAccordion();
});

async function fetchGitHubRelease() {
  const versionTags = document.querySelectorAll('.release-version-tag');
  const directDownloadLinks = document.querySelectorAll('.direct-download-link');
  
  const REPO = 'p5Patricio/WhisperKey';
  const FALLBACK_VERSION = 'v1.2.0';
  const FALLBACK_DOWNLOAD = `https://github.com/${REPO}/releases/latest/download/WhisperKey-Setup.exe`;

  directDownloadLinks.forEach(link => {
    link.setAttribute('href', FALLBACK_DOWNLOAD);
  });

  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`);
    if (!res.ok) return;
    const data = await res.json();
    const tag = data.tag_name || FALLBACK_VERSION;
    
    versionTags.forEach(el => {
      el.textContent = tag;
    });

    const exeAsset = data.assets?.find(a => a.name.endsWith('.exe'));
    if (exeAsset && exeAsset.browser_download_url) {
      directDownloadLinks.forEach(link => {
        link.setAttribute('href', exeAsset.browser_download_url);
      });
    }
  } catch (err) {
    console.debug('GitHub release fetch error (using fallback):', err);
  }
}

function initDictationSimulator() {
  const triggerBtn = document.getElementById('demo-hotkey-btn');
  const outputEl = document.getElementById('editor-output-text');
  const statusEl = document.getElementById('demo-status-text');
  const waveEl = document.getElementById('demo-soundwave');

  if (!triggerBtn || !outputEl) return;

  const sampleTexts = [
    'Hacé un git push al branch de staging, deployá en Kubernetes y corré los tests de integración.',
    'Revisá el pull request de autenticación, agregá los logs en el backend y verificá el endpoint de Whisper.',
    'Creá una nueva migración en PostgreSQL para los usuarios activos y optimizá las queries con un índice.'
  ];
  let sampleIndex = 0;
  let isRecording = false;
  let typeInterval = null;

  function startRecording() {
    if (isRecording) return;
    isRecording = true;
    triggerBtn.classList.add('active');
    triggerBtn.querySelector('.btn-label').textContent = 'Escuchando...';
    if (statusEl) statusEl.textContent = '● Grabando voz';
    if (waveEl) waveEl.style.display = 'inline-flex';
  }

  function stopRecording() {
    if (!isRecording) return;
    isRecording = false;
    triggerBtn.classList.remove('active');
    triggerBtn.querySelector('.btn-label').textContent = 'Presionar F9 para dictar';
    if (statusEl) statusEl.textContent = '✓ Transcrito';
    if (waveEl) waveEl.style.display = 'none';

    // Type out the transcription
    const targetText = sampleTexts[sampleIndex % sampleTexts.length];
    sampleIndex++;
    
    outputEl.textContent = '';
    let charIndex = 0;
    clearInterval(typeInterval);
    
    typeInterval = setInterval(() => {
      if (charIndex < targetText.length) {
        outputEl.textContent += targetText[charIndex];
        charIndex++;
      } else {
        clearInterval(typeInterval);
      }
    }, 28);
  }

  // Click toggle or hold
  triggerBtn.addEventListener('mousedown', startRecording);
  window.addEventListener('mouseup', () => {
    if (isRecording) stopRecording();
  });

  // Touch events for mobile
  triggerBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    startRecording();
  });
  triggerBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRecording();
  });

  // Global F9 keyboard listener while on the webpage
  window.addEventListener('keydown', (e) => {
    if (e.key === 'F9' || e.code === 'F9') {
      e.preventDefault();
      startRecording();
    }
  });
  window.addEventListener('keyup', (e) => {
    if (e.key === 'F9' || e.code === 'F9') {
      e.preventDefault();
      stopRecording();
    }
  });
}

function initFaqAccordion() {
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const questionBtn = item.querySelector('.faq-question');
    questionBtn?.addEventListener('click', () => {
      const isOpen = item.classList.contains('open');
      faqItems.forEach(i => i.classList.remove('open'));
      if (!isOpen) {
        item.classList.add('open');
      }
    });
  });
}
