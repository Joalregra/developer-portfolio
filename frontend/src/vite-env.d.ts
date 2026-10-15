/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  /** Public origin of the site (https://example.com), used for canonical, hreflang and the sitemap. */
  readonly VITE_SITE_URL?: string
}

/** Month of the build as `YYYY-MM`, injected by Vite (`define`). */
declare const __BUILD_DATE__: string

interface ImportMeta {
  readonly env: ImportMetaEnv
}
