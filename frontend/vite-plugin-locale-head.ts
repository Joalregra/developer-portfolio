import type { Plugin } from 'vite'
import { profile, type Locale } from './src/data/profile.ts'
import { siteMeta } from './src/i18n/meta.ts'

const OG_LOCALE: Record<Locale, string> = { es: 'es_CO', en: 'en_US' }

function escapeAttr(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
}

function pageLocale(path: string): Locale | null {
  const match = /^\/(es|en)(\/|$)/.exec(path)
  return match ? (match[1] as Locale) : null
}

function jsonLd(locale: Locale, siteUrl?: string): string {
  const person = {
    '@context': 'https://schema.org',
    '@type': 'Person',
    name: profile.name,
    jobTitle: profile.role[locale],
    email: `mailto:${profile.email}`,
    ...(siteUrl ? { url: `${siteUrl}/${locale}/` } : {}),
    sameAs: [profile.links.linkedin, profile.links.github],
    address: {
      '@type': 'PostalAddress',
      addressLocality: 'San José',
      addressRegion: 'Caldas',
      addressCountry: 'CO',
    },
    knowsLanguage: ['es', 'en'],
  }
  // `<` is escaped so the JSON can never close the script element early.
  return JSON.stringify(person).replace(/</g, '\\u003c')
}

function headFor(locale: Locale | null, siteUrl?: string): string {
  // The root page is the x-default entry; it carries the English metadata.
  const lang: Locale = locale ?? 'en'
  const meta = siteMeta[lang]
  const base = siteUrl ?? ''
  const image = `${base}/og/og-${lang}.png`
  const lines = [
    `<title>${escapeAttr(meta.title)}</title>`,
    `<meta name="description" content="${escapeAttr(meta.description)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:title" content="${escapeAttr(meta.title)}" />`,
    `<meta property="og:description" content="${escapeAttr(meta.description)}" />`,
    `<meta property="og:locale" content="${OG_LOCALE[lang]}" />`,
    `<meta property="og:image" content="${image}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta property="og:image:alt" content="${escapeAttr(meta.ogAlt)}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
  ]
  if (siteUrl) {
    lines.push(
      `<link rel="canonical" href="${siteUrl}/${locale ? `${locale}/` : ''}" />`,
      `<link rel="alternate" hreflang="es" href="${siteUrl}/es/" />`,
      `<link rel="alternate" hreflang="en" href="${siteUrl}/en/" />`,
      `<link rel="alternate" hreflang="x-default" href="${siteUrl}/" />`,
    )
  }
  lines.push(`<script type="application/ld+json">${jsonLd(lang, siteUrl)}</script>`)
  return lines.join('\n    ')
}

function sitemap(siteUrl: string): string {
  const alternates = [
    `<xhtml:link rel="alternate" hreflang="es" href="${siteUrl}/es/" />`,
    `<xhtml:link rel="alternate" hreflang="en" href="${siteUrl}/en/" />`,
    `<xhtml:link rel="alternate" hreflang="x-default" href="${siteUrl}/" />`,
  ].join('')
  const urls = ['es', 'en']
    .map((code) => `<url><loc>${siteUrl}/${code}/</loc>${alternates}</url>`)
    .join('')
  return `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">${urls}</urlset>\n`
}

/**
 * Writes the per-language head (title, description, Open Graph, hreflang, JSON-LD) into the
 * static HTML so crawlers and link previews do not need to run JavaScript. Absolute URLs need
 * VITE_SITE_URL; without it the canonical/hreflang tags and the sitemap are skipped.
 */
export function localeHead(siteUrl?: string): Plugin {
  return {
    name: 'locale-head',
    transformIndexHtml: {
      order: 'pre',
      handler(html, ctx) {
        return html.replace('<!--LOCALE_HEAD-->', headFor(pageLocale(ctx.path), siteUrl))
      },
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'robots.txt',
        source: `User-agent: *\nAllow: /\n${siteUrl ? `\nSitemap: ${siteUrl}/sitemap.xml\n` : ''}`,
      })
      if (siteUrl)
        this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap(siteUrl) })
    },
  }
}
