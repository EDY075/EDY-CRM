import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  // Builds locais não apagam chunks que abas abertas ainda podem carregar.
  // A nova entrada usa os novos hashes; formulários abertos continuam funcionais.
  build: { emptyOutDir: false },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5178,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5128",
        changeOrigin: true,
      },
    },
  },
})
