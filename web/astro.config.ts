import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import react from "@astrojs/react";

export default defineConfig({
  site: import.meta.env.PUBLIC_SITE_URL || "https://finalsmvp.netlify.app",
  integrations: [
    tailwind({
      applyBaseStyles: false,
    }),
    react(),
  ],
});
