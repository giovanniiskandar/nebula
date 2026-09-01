import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Production loads over file://, where Vite's default absolute /assets/...
  // paths resolve against the filesystem root and the window renders blank.
  base: './',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // Fail instead of hopping to 5174, which app.py would not be watching.
    strictPort: true,
  },
})
