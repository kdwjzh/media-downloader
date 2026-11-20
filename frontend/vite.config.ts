import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The licenses of the npm packages bundled into dist/; the installer ships them.
  build: { license: { fileName: 'third-party-licenses.md' } },
})
