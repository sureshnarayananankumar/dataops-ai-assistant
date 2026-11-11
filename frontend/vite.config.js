import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite = the dev server + build tool for the React app.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
