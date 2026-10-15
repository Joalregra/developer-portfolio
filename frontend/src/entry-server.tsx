import { renderToString } from 'react-dom/server'
import App from './app/App'
import type { Locale } from './data/profile'

/** Used only at build time (scripts/prerender.mjs) to put the page content in the static HTML. */
export function render(locale: Locale): string {
  return renderToString(<App initialLocale={locale} />)
}
