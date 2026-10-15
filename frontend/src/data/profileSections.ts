import type { Localized } from './profile'
import type { ProjectId } from './projects'

export interface ExperienceEntry {
  id: string
  role: Localized
  organization: string
  city?: string
  period: { start: string; end: string }
  bullets: Localized<string[]>
  projectIds: ProjectId[]
}

export const experience: ExperienceEntry[] = [
  {
    id: 'globant',
    role: { es: 'Desarrollador FullStack Practicante', en: 'FullStack Developer Trainee' },
    organization: 'Globant',
    city: 'Pereira, Colombia',
    period: { start: '2026-04', end: '2026-10' },
    bullets: {
      es: [
        'Desarrollé servicios backend y endpoints REST con Python, FastAPI y PostgreSQL, integrados con interfaces en React y TypeScript.',
        'Trabajé en dos productos internos de innovación, cada uno con un equipo de **3 personas**, con Spec-Driven Development y prácticas Agile/Scrum.',
        'La plataforma de reportes con IA se desplegó y corre en producción; se entregó a un equipo interno para su mantenimiento diario.',
      ],
      en: [
        'I developed backend services and REST endpoints with Python, FastAPI and PostgreSQL, integrated with React and TypeScript interfaces.',
        'I worked on two internal innovation products, each with a team of **3 people**, using Spec-Driven Development and Agile/Scrum practices.',
        'The AI reporting platform was deployed and runs in production; it was handed to an internal team for daily maintenance.',
      ],
    },
    projectIds: ['reports', 'intel'],
  },
  {
    id: 'sena',
    role: {
      es: 'Proyecto académico para un cliente real: QA y frontend',
      en: 'Academic project for a real client: QA and frontend',
    },
    organization: 'SENA',
    period: { start: '2024-07', end: '2026-04' },
    bullets: {
      es: [
        'Participé en Gedocs, un sistema de archivo documental y PQRSD, con un equipo de **9 personas** y unos **60 usuarios** reales.',
        'Hice QA full stack, creé maquetas e interfaces en React y lideré la suite de pruebas (PHPUnit y Vitest).',
      ],
      en: [
        'I took part in Gedocs, a document archiving and PQRSD system, with a team of **9 people** and about **60 real users**.',
        'I did full stack QA, created mockups and React interfaces, and led the test suite (PHPUnit and Vitest).',
      ],
    },
    projectIds: ['gedocs'],
  },
]

export type SkillGroupId = 'production' | 'projects' | 'learning' | 'tools'

export interface Skill {
  name: string
  usedIn?: ProjectId[]
}

export interface SkillGroup {
  id: SkillGroupId
  skills: Skill[]
}

// The group names and members are a proposal to be confirmed by Johan (see the design brief, SKILL-02).
export const skillGroups: SkillGroup[] = [
  {
    id: 'production',
    skills: [
      { name: 'Python', usedIn: ['reports', 'intel'] },
      { name: 'FastAPI', usedIn: ['reports', 'intel'] },
      { name: 'PostgreSQL', usedIn: ['reports', 'intel'] },
      { name: 'React', usedIn: ['reports', 'intel', 'gedocs'] },
      { name: 'TypeScript', usedIn: ['reports', 'intel'] },
      { name: 'Docker', usedIn: ['gedocs'] },
      { name: 'Dokploy', usedIn: ['gedocs'] },
      { name: 'DigitalOcean', usedIn: ['gedocs'] },
    ],
  },
  {
    id: 'projects',
    skills: [
      'Laravel',
      'MySQL',
      'Node.js',
      'pytest',
      'Vitest',
      'React Testing Library',
      'MSW',
      'PHPUnit',
      'SQLAlchemy',
      'Pydantic',
      'pgvector',
      'Zustand',
      'TanStack Query',
      'Tailwind',
      'WordPress',
    ].map((name) => ({ name })),
  },
  {
    id: 'learning',
    skills: ['AWS', 'Jenkins', 'Terraform', 'GitHub Actions'].map((name) => ({ name })),
  },
  {
    id: 'tools',
    skills: ['Git', 'GitHub', 'GitLab', 'Jira', 'Trello', 'Figma'].map((name) => ({ name })),
  },
]

export interface Certification {
  id: string
  /** Official title, kept in its original language (I18N-02). */
  name: string
  issuer: string
  /** ISO month, or null when the certificate shows no date. */
  date: string | null
  /** Extra fact shown under the title, such as a score. */
  detail?: Localized
  /** Public verification URL. Without one the entry is listed with no button (EDU-02). */
  verifyUrl: string | null
  /** PDF of the certificate in /public/certs, with its size in KB. Opens in a new tab. */
  pdf?: { href: string; kb: number }
}

export const education = {
  degree: {
    es: 'Tecnólogo en Análisis y Desarrollo de Software',
    en: 'Associate degree in Software Analysis and Development',
  } satisfies Localized,
  school: 'SENA',
  period: { start: '2024-07', end: '2026-10' },
  note: {
    es: 'Etapas lectiva y productiva completadas; título pendiente de resultados Saber TyT.',
    en: 'Classroom and work-placement stages completed; degree pending Saber TyT results.',
  } satisfies Localized,
  languages: {
    es: 'Español nativo, inglés A2 (puedo hacer una entrevista en inglés).',
    en: 'Native Spanish, English A2 (I can do an interview in English).',
  } satisfies Localized,
}

// From the PDF certificates. None of them has a public verification link.
export const certifications: Certification[] = [
  {
    id: 'anthropic-ai-fluency',
    name: 'AI Fluency: Framework & Foundations',
    issuer: 'Anthropic',
    date: null,
    verifyUrl: 'https://academy.claude.com/verify/71f83beb90b7405c3d910d2a41ab38ef',
    pdf: { href: '/certs/anthropic-ai-fluency-framework-foundations.pdf', kb: 146 },
  },
  {
    id: 'globant-ai-fluency-score',
    name: 'AI Fluency Questionnaire',
    issuer: 'Globant',
    date: '2026-09',
    detail: { es: 'Puntaje: 99,6 / 100', en: 'Score: 99.6 / 100' },
    verifyUrl: null,
  },
  ...(
    [
      [
        'context-engineering',
        'Advance Context Engineering',
        '2026-09',
        'globant-advance-context-engineering',
      ],
      ['agent-skills', 'AI Agent Skills', '2026-09', 'globant-ai-agent-skills'],
      ['ai-literacy', 'AI Literacy Foundations', '2026-09', 'globant-ai-literacy-foundations'],
      [
        'anthropic-ai-fluency-gu',
        "Anthropic's AI Fluency",
        '2026-09',
        'globant-anthropics-ai-fluency',
      ],
      [
        'ai-coding-workflows',
        'Building AI Coding Workflows & Optimizations',
        '2026-08',
        'globant-ai-coding-workflows',
      ],
      [
        'ai-assisted-development',
        'AI-Assisted Development Foundations',
        '2026-08',
        'globant-ai-assisted-development',
      ],
    ] as const
  ).map(([id, name, date, file]) => ({
    id,
    name,
    issuer: 'Globant University',
    date,
    verifyUrl: null,
    pdf: { href: `/certs/${file}.pdf`, kb: 225 },
  })),
]
