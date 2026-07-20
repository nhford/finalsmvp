import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import react from "@astrojs/react";

export default defineConfig({
  // Optional: PUBLIC_SITE_URL=https://your-domain at build for canonical / OG URLs.
  site: import.meta.env.PUBLIC_SITE_URL || undefined,
  integrations: [
    tailwind({
      applyBaseStyles: false,
    }),
    react(),
  ],
});
