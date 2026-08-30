import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serves a project site under /<repo-name>/, not the domain root.
  base: '/cnpj-due-diligence/',
  plugins: [react()],
})
