# WhisperKey — Landing Page

Sitio de marketing de WhisperKey (dictado por voz local para Windows). Vite + React + TypeScript.

## Stack

Vite, React 19, TypeScript, PNPM (obligatorio para todo trabajo en este directorio — ver AGENTS.md en la raíz del repo).

## Desarrollo local

```bash
pnpm install
pnpm dev        # http://localhost:5173
```

## Build y deploy (manual — no hay CI/CD)

1. Limpiar `../docs/assets/` (borra los chunks JS/CSS viejos del build anterior). **No borrar los `.md` de `../docs/`** — `MARKETING_COPY.md` y `testing-checklist.md` viven ahí pero no son output del build.
2. `pnpm build` — corre `tsc -b && vite build`, escribe el output en `../docs`.
3. `pnpm preview` — verificar localmente antes de commitear.
4. Desde la raíz del repo: commit + push a `main`.
5. GitHub Pages sirve `main:/docs` directamente, sin Action — el sitio se actualiza solo tras el push.

## Por qué `emptyOutDir` es `false`

`vite.config.ts` tiene `emptyOutDir: false` a propósito: `../docs/` también contiene los `.md` de arriba, que no son output de Vite. Vaciar todo el `outDir` en cada build los borraría. Por eso el paso 1 de arriba limpia manualmente solo `docs/assets/`, en vez de usar `emptyOutDir: true`.

Sitio en producción: https://p5patricio.github.io/WhisperKey/
