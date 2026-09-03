/// <reference types="vitest/config" />
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    // Backend: uvicorn magda.api:app --reload (Port 8000)
    // MAGDA_API erlaubt eine zweite Instanz neben einem fremden Server auf 8000.
    proxy: { "/api": process.env.MAGDA_API ?? "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
})
