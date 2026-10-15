export type Locale = 'es' | 'en'
export type Localized<T = string> = Record<Locale, T>

export const locales: readonly Locale[] = ['es', 'en']

export interface CvFile {
  href: string
  pages: number
}

export interface Profile {
  name: string
  shortName: string
  role: Localized
  location: Localized
  availability: Localized
  valueProp: Localized
  email: string
  links: {
    linkedin: string
    github: string
    repo: string
  }
  cv: Localized<CvFile>
}

export const profile: Profile = {
  name: 'Johan Alexis Rendon Granada',
  shortName: 'Johan Rendon',
  role: {
    es: 'Desarrollador Backend Junior (Python, FastAPI) con experiencia en React',
    en: 'Junior Backend Developer (Python, FastAPI) with React experience',
  },
  location: {
    es: 'San José, Caldas, Colombia (GMT-5)',
    en: 'San José, Caldas, Colombia (GMT-5)',
  },
  availability: {
    es: 'Disponible para contratación inmediata. Remoto o híbrido.',
    en: 'Available for immediate hiring. Remote or hybrid.',
  },
  valueProp: {
    es: 'Construyo backends con FastAPI e interfaces con React, con experiencia en pipelines de IA, búsqueda semántica (RAG) y pruebas automatizadas.',
    en: 'I build FastAPI backends and React interfaces, with experience in AI pipelines, RAG semantic search and automated testing.',
  },
  email: 'johanalexis808@gmail.com',
  links: {
    linkedin: 'https://www.linkedin.com/in/johan-rendon-granada-14b8a82bb',
    github: 'https://github.com/Joalregra',
    repo: 'https://github.com/Joalregra/developer-portfolio',
  },
  cv: {
    es: { href: '/cv/Johan-Rendon-Granada-CV-ES.pdf', pages: 1 },
    en: { href: '/cv/Johan-Rendon-Granada-CV-EN.pdf', pages: 1 },
  },
}
