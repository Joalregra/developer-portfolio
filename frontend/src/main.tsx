import { StrictMode } from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import App from './app/App'
import { localeFromPath } from './i18n/locale'
import './styles/index.css'

const container = document.getElementById('root')!
const app = (
  <StrictMode>
    <App initialLocale={localeFromPath(window.location.pathname) ?? undefined} />
  </StrictMode>
)

// /es/ and /en/ ship with the page already rendered, so React only attaches to it.
// The root URL is empty: it picks the language and renders on the client.
if (container.hasChildNodes()) hydrateRoot(container, app)
else createRoot(container).render(app)
