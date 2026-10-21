import type { Locale } from '../data/profile.ts'

// Shared by the runtime (document title) and by the build (static head of each language page).
export const siteMeta: Record<Locale, { title: string; description: string; ogAlt: string }> = {
  es: {
    title: 'Johan Rendon | Desarrollador Backend Junior (Python, FastAPI)',
    description:
      'Portafolio de Johan Rendon, desarrollador backend junior. Construyo backends con FastAPI e interfaces con React, con pipelines de IA, búsqueda RAG y pruebas.',
    ogAlt: 'Johan Rendon, desarrollador backend junior con Python y FastAPI',
  },
  en: {
    title: 'Johan Rendon | Junior Backend Developer (Python, FastAPI)',
    description:
      'Portfolio of Johan Rendon, junior backend developer. I build FastAPI backends and React interfaces, with AI pipelines, RAG search and automated tests.',
    ogAlt: 'Johan Rendon, junior backend developer with Python and FastAPI',
  },
}
