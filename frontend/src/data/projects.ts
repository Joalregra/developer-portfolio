import type { Localized } from './profile'

export type ProjectId = 'reports' | 'intel' | 'gedocs'

/**
 * production: runs for real users and can be named without restriction.
 * nda: work done at Globant, covered by an NDA (no public code or demo).
 */
export type ProjectStatus = 'production' | 'nda'

export interface ProjectScreenshot {
  /** Path under `public/`, served as is. */
  src: string
  width: number
  height: number
  alt: Localized
  caption: Localized
}

/** Public demo with fictitious data. Only Gedocs has one. */
export interface ProjectDemo {
  url: string
  screenshots: ProjectScreenshot[]
}

export interface Project {
  id: ProjectId
  name: Localized
  /** Short label for cross-references (skills, experience). */
  shortName: Localized
  tagline: Localized
  /** ISO months, formatted with Intl at render time. */
  period: { start: string; end: string }
  role: Localized
  team: number
  status: ProjectStatus
  /** Only the reports platform is stated to run in production in the company's private environment. */
  runsInPrivateProduction: boolean
  demo?: ProjectDemo
  problem: Localized
  /** Strings may wrap figures in **double asterisks** to render them in bold. */
  did: Localized<string[]>
  decision: { title: Localized; body: Localized }
  result: Localized
  /** At most 8 visible badges; the rest live in the technical detail. */
  stack: string[]
  stackMore: string[]
  /** Question sent to the assistant from the "Ask the assistant about this project" link. */
  question: Localized
  diagram: boolean
}

// Order is intentional (PROJ-01): relevance for a Python backend role, then impact.
export const projects: Project[] = [
  {
    id: 'reports',
    name: {
      es: 'Plataforma de reportes de inteligencia de producto con IA',
      en: 'AI product intelligence reporting platform',
    },
    shortName: { es: 'Plataforma de reportes con IA', en: 'AI reporting platform' },
    tagline: {
      es: 'Genera reportes estructurados de producto con un pipeline de IA de varias fases y búsqueda semántica sobre ellos.',
      en: 'Generates structured product reports with a multi-phase AI pipeline and semantic search over them.',
    },
    period: { start: '2026-06', end: '2026-10' },
    role: {
      es: 'Desarrollador FullStack Practicante en Globant (backend, frontend e IA)',
      en: 'FullStack Developer Trainee at Globant (backend, frontend and AI)',
    },
    team: 3,
    status: 'nda',
    runsInPrivateProduction: true,
    problem: {
      es: 'Reunir datos de catálogos externos, búsqueda web y modelos de lenguaje en reportes estructurados de producto, y poder buscar dentro de ellos viendo de dónde sale cada fragmento.',
      en: 'Bring data from external catalogs, web search and language models into structured product reports, and search inside them while seeing where each fragment comes from.',
    },
    did: {
      es: [
        'Construí el pipeline del Full Report: **10 lentes** de investigación y etiquetado sobre un solo reporte, con exportación a PDF en el servidor.',
        'Diseñé la búsqueda semántica (RAG): fragmentos con límites tomados del contenido, embeddings locales, recuperación híbrida (densa y léxica) y la procedencia de cada fragmento (producto, categoría, fuente y fecha).',
        'Implementé el inicio de sesión con cookies httpOnly y protección CSRF, y los roles admin y developer, con una transferencia atómica del rol de admin para que nunca falte un administrador.',
        'Construí las notificaciones, la administración de roles y la administración de la búsqueda semántica.',
      ],
      en: [
        'I built the Full Report pipeline: **10 research and tagging lenses** over one report, with server-side PDF export.',
        'I designed the semantic search (RAG): chunks split by content boundaries, local embeddings, hybrid retrieval (dense and lexical) and the provenance of each chunk (product, category, source and date).',
        'I implemented login with httpOnly cookies and CSRF protection, and the admin and developer roles, with an atomic admin transfer so the system never loses its last admin.',
        'I built the notifications, the role administration and the semantic search administration.',
      ],
    },
    decision: {
      title: {
        es: 'Decisión técnica: failover entre proveedores de LLM',
        en: 'Technical decision: failover between LLM providers',
      },
      body: {
        es: 'Diseñé una capa de enrutamiento entre proveedores de LLM con failover automático y control de concurrencia por proveedor. Además guarda el uso de tokens de cada llamada, con un endpoint y un dashboard de administración.',
        en: 'I designed a routing layer between LLM providers with automatic failover and per-provider concurrency control. It also stores the token usage of each call, with an endpoint and an admin dashboard.',
      },
    },
    result: {
      es: 'Desplegada y en producción en el entorno privado de la empresa. Se entregó a un equipo interno para su mantenimiento diario.',
      en: "Deployed and running in production in the company's private environment. It was handed to an internal team for daily maintenance.",
    },
    stack: ['Python', 'FastAPI', 'PostgreSQL', 'pgvector', 'React', 'TypeScript', 'Gemini', 'Groq'],
    stackMore: [
      'SQLAlchemy',
      'Pydantic',
      'fastembed',
      'pytest',
      'Vite',
      'Zustand',
      'Tailwind',
      'Vitest',
    ],
    question: {
      es: '¿Qué hizo Johan en la plataforma de reportes de inteligencia de producto con IA?',
      en: 'What did Johan do on the AI product intelligence reporting platform?',
    },
    diagram: true,
  },
  {
    id: 'intel',
    name: {
      es: 'Plataforma de inteligencia competitiva',
      en: 'Competitive intelligence platform',
    },
    shortName: { es: 'Inteligencia competitiva', en: 'Competitive intelligence' },
    tagline: {
      es: 'Recopila publicaciones de comunidades de desarrolladores, las analiza con IA y muestra sentimiento, riesgo de churn, NPS y alertas.',
      en: 'Collects posts from developer communities, analyzes them with AI and shows sentiment, churn risk, NPS and alerts.',
    },
    period: { start: '2026-04', end: '2026-06' },
    role: {
      es: 'Desarrollador FullStack Practicante en Globant',
      en: 'FullStack Developer Trainee at Globant',
    },
    team: 3,
    status: 'nda',
    runsInPrivateProduction: false,
    problem: {
      es: 'Convertir publicaciones sueltas de foros y comunidades en métricas que un equipo pueda consultar: sentimiento, riesgo de abandono (churn), NPS y alertas.',
      en: 'Turn loose posts from forums and communities into metrics a team can query: sentiment, churn risk, NPS and alerts.',
    },
    did: {
      es: [
        'Diseñé **11 endpoints REST** con FastAPI para listar publicaciones y consultar sus métricas. Los filtros y la paginación se ejecutan en SQL, no en memoria.',
        'Construí los endpoints de ingesta por producto: buscan, analizan con el LLM y guardan los resultados en PostgreSQL.',
        'Construí el feed en vivo en React, con paginación, filtros, búsqueda y estadísticas.',
        'Escribí las pruebas: **25 de backend** (pytest) y **29 de frontend** (Vitest, React Testing Library y MSW). La infraestructura de pruebas del frontend la armé desde cero.',
        'Documenté el esquema, la integración del frontend y las pruebas para que el equipo pudiera mantenerlos.',
      ],
      en: [
        'I designed **11 REST endpoints** with FastAPI to list posts and query their metrics. Filters and pagination run in SQL, not in memory.',
        'I built the per-product ingestion endpoints: they search, analyze with the LLM and store the results in PostgreSQL.',
        'I built the live feed in React, with pagination, filters, search and statistics.',
        'I wrote the tests: **25 backend** (pytest) and **29 frontend** (Vitest, React Testing Library and MSW). I built the frontend test setup from scratch.',
        'I documented the schema, the frontend integration and the tests so the team could maintain them.',
      ],
    },
    decision: {
      title: {
        es: 'Decisión técnica: salida estructurada de Gemini',
        en: 'Technical decision: structured output from Gemini',
      },
      body: {
        es: 'Gemini rechazaba los JSON Schema de Pydantic con referencias ($ref, $defs), uniones (anyOf) y constantes (const), y las respuestas no eran JSON válido. Escribí un resolver que aplana el esquema a un formato que el modelo acepta.',
        en: 'Gemini rejected Pydantic JSON Schemas with references ($ref, $defs), unions (anyOf) and constants (const), so the answers were not valid JSON. I wrote a resolver that flattens the schema to a format the model accepts.',
      },
    },
    result: {
      es: '54 pruebas aprobadas (25 de backend y 29 de frontend) y documentación del esquema, de la integración y de las pruebas.',
      en: '54 passing tests (25 backend and 29 frontend) and documentation of the schema, the integration and the tests.',
    },
    stack: [
      'Python',
      'FastAPI',
      'PostgreSQL',
      'SQLAlchemy',
      'Pydantic',
      'Gemini',
      'React',
      'TypeScript',
    ],
    stackMore: [
      'pytest',
      'Vite',
      'TanStack Query',
      'Zustand',
      'Tailwind',
      'Vitest',
      'React Testing Library',
      'MSW',
    ],
    question: {
      es: '¿Qué hizo Johan en la plataforma de inteligencia competitiva?',
      en: 'What did Johan do on the competitive intelligence platform?',
    },
    diagram: true,
  },
  {
    id: 'gedocs',
    name: { es: 'Gedocs', en: 'Gedocs' },
    shortName: { es: 'Gedocs', en: 'Gedocs' },
    tagline: {
      es: 'Sistema web institucional de archivo documental y gestión de PQRSD para el SENA.',
      en: 'Institutional web system for document archiving and PQRSD management for SENA.',
    },
    period: { start: '2024-07', end: '2026-04' },
    role: {
      es: 'QA full stack y frontend: maquetas e interfaces en React. Lideré la suite de pruebas.',
      en: 'Full stack QA and frontend: mockups and React interfaces. I led the test suite.',
    },
    team: 9,
    status: 'production',
    runsInPrivateProduction: false,
    demo: {
      url: 'https://gedocs.johanrendon.com/',
      screenshots: [
        {
          src: '/img/gedocs/login.webp',
          width: 1440,
          height: 900,
          alt: {
            es: 'Pantalla de inicio de sesión de Gedocs, con cuatro botones para entrar sin registro según el rol.',
            en: 'Gedocs login screen, with four buttons to sign in without registering, by role.',
          },
          caption: {
            es: 'Entrada sin registro: eliges un rol y recorres el sistema.',
            en: 'Sign-in without registering: pick a role and explore the system.',
          },
        },
        {
          src: '/img/gedocs/inbox.webp',
          width: 1440,
          height: 900,
          alt: {
            es: 'Bandeja de entrada de PQRSD con filtros por tipo, el detalle del solicitante y el campo para responder.',
            en: 'PQRSD inbox with filters by type, the requester details and the reply field.',
          },
          caption: {
            es: 'Bandeja de PQRSD: filtros por tipo, fecha límite y respuesta.',
            en: 'PQRSD inbox: filters by type, deadline and reply.',
          },
        },
        {
          src: '/img/gedocs/explorer.webp',
          width: 1440,
          height: 900,
          alt: {
            es: 'Explorador de archivo documental, con las entidades a la izquierda y las dependencias de la entidad elegida como carpetas.',
            en: 'Document archive explorer, with the entities on the left and the departments of the chosen entity as folders.',
          },
          caption: {
            es: 'Archivo documental por entidad y dependencia, como un drive.',
            en: 'Document archive by entity and department, like a drive.',
          },
        },
        {
          src: '/img/gedocs/pdf-generator.webp',
          width: 1440,
          height: 900,
          alt: {
            es: 'Generador de oficios en PDF, con una carta que tiene campos para el destinatario, el asunto y el cuerpo.',
            en: 'PDF letter generator, with a letter that has fields for the recipient, subject and body.',
          },
          caption: {
            es: 'Generador de oficios: llenas la carta y se exporta a PDF.',
            en: 'Letter generator: fill in the letter and export it to PDF.',
          },
        },
      ],
    },
    problem: {
      es: 'El área de gestión documental del SENA necesitaba archivar documentos como en un drive y gestionar PQRSD (peticiones, quejas, reclamos, sugerencias y denuncias), conforme a la Ley General de Archivos de Colombia.',
      en: 'The document management area of SENA needed to archive documents like in a drive and manage PQRSD (petitions, complaints, claims, suggestions and reports), following the Colombian General Archives Law.',
    },
    did: {
      es: [
        'Hice QA full stack: probé el frontend y el backend.',
        'Creé las maquetas y diseñé varias interfaces en React.',
        'Lideré la suite de pruebas: PHPUnit en el backend y Vitest en el frontend.',
        'Desplegué el sistema a producción en DigitalOcean, en contenedores con Dokploy.',
      ],
      en: [
        'I did full stack QA: I tested both the frontend and the backend.',
        'I created the mockups and designed several React interfaces.',
        'I led the test suite: PHPUnit on the backend and Vitest on the frontend.',
        'I deployed the system to production on DigitalOcean, in containers with Dokploy.',
      ],
    },
    decision: {
      title: {
        es: 'Reto: requisitos poco claros al comienzo',
        en: 'Challenge: unclear requirements at the start',
      },
      body: {
        es: 'Un error de comunicación con el cliente duplicó trabajo: se construyeron funciones para metodologías que el cliente no quería. El equipo hizo una reunión de aclaración y corregir tomó un par de días. Desde entonces hacemos preguntas constantes al cliente y documentamos cada acuerdo por escrito.',
        en: 'A communication mistake with the client doubled the work: we built features for methods the client did not want. The team held a clarification meeting and fixing it took a couple of days. Since then we ask the client constant questions and write down every agreement.',
      },
    },
    result: {
      es: 'En producción, con unos **60 usuarios** reales. Equipo de **9 personas**.',
      en: 'In production, with about **60 real users**. Team of **9 people**.',
    },
    stack: ['Laravel', 'React', 'MySQL', 'PHPUnit', 'Vitest', 'DigitalOcean', 'Dokploy'],
    stackMore: [],
    question: {
      es: '¿Qué hizo Johan en Gedocs?',
      en: 'What did Johan do on Gedocs?',
    },
    diagram: false,
  },
]
