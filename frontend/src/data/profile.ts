export type Locale = 'es' | 'en'

export interface Profile {
  name: string
  role: Record<Locale, string>
  location: Record<Locale, string>
  email: string
  links: {
    linkedin: string
    github: string
    cv: string
  }
}

export const profile: Profile = {
  name: 'Johan Alexis Rendon Granada',
  role: {
    es: 'Desarrollador Backend Junior (Python, FastAPI) con experiencia en React',
    en: 'Junior Backend Developer (Python, FastAPI) with React experience',
  },
  location: {
    es: 'San José, Caldas, Colombia · GMT-5',
    en: 'San Jose, Caldas, Colombia · GMT-5',
  },
  email: 'johanalexis808@gmail.com',
  links: {
    linkedin: 'https://www.linkedin.com/in/johan-rendon-granada-14b8a82bb',
    github: 'https://github.com/Joalregra',
    cv: '/cv/Johan-Rendon-Granada-CV-EN.pdf',
  },
}
