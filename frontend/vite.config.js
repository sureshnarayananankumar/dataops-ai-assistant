import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite = the dev server + build tool for the React app.
// `base` is "/" locally and "/dataops-ai-assistant/" for the GitHub Pages build.
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: { port: 5173 },
});
