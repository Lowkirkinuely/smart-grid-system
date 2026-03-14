import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { viteCommonjs } from '@originjs/vite-plugin-commonjs'

export default defineConfig({
  plugins: [react(), viteCommonjs()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  optimizeDeps: {
    include: [
      'react-simple-maps', 
      'recharts', 
      'prop-types', 
      'react-is',
      'd3-geo',
      'd3-selection'
    ],
  },
  build: {
    commonjsOptions: {
      transformMixedEsModules: true,
    },
  },
})
