import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages 项目站：https://<user>.github.io/<repo>/
// 本地开发保持 base = "/"
const base = process.env.VITE_BASE || "/";

export default defineConfig({
  plugins: [react()],
  base,
});
