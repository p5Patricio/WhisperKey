import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: '../docs',
    // true: docs/ pasa a ser salida pura de Vite. Con false, cada build dejaba
    // el bundle anterior olvidado ahí y se juntaron seis. Todo lo que no genera
    // Vite vive en web/public/ y se copia en cada build.
    emptyOutDir: true,
  },

})
