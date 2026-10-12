import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

import { resolveApiBaseUrl } from "./src/api/apiBaseUrl.ts";

export default defineConfig(({ command, mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), "VITE_");
  const configured = process.env.VITE_API_URL ?? fileEnv.VITE_API_URL;
  resolveApiBaseUrl(
    configured,
    command === "build" ? "production" : "development",
  );

  return {
    plugins: [
      react(),
      tailwindcss(),
    ],
  };
});