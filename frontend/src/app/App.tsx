import { Footer } from '../components/layout/Footer'
import { Header } from '../components/layout/Header'
import { ChatProvider } from '../features/chat/ChatProvider'
import { useLocale } from '../hooks/useLocale'
import { LocaleProvider } from '../i18n/LocaleProvider'
import { About } from '../sections/About'
import { Contact } from '../sections/Contact'
import { Education } from '../sections/Education'
import { Experience } from '../sections/Experience'
import { Hero } from '../sections/Hero'
import { Projects } from '../sections/Projects'
import { Skills } from '../sections/Skills'
import type { Locale } from '../data/profile'

function Page() {
  const { t } = useLocale()
  return (
    <>
      <a
        href="#main"
        data-print="hide"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-ink focus:px-4 focus:py-3 focus:font-semibold focus:text-paper"
      >
        {t.skip}
      </a>
      <Header />
      <main id="main" tabIndex={-1}>
        <Hero />
        <Projects />
        <Experience />
        <About />
        <Skills />
        <Education />
        <Contact />
      </main>
      <Footer />
    </>
  )
}

export default function App({ initialLocale }: { initialLocale?: Locale }) {
  return (
    <LocaleProvider initialLocale={initialLocale}>
      <ChatProvider>
        <Page />
      </ChatProvider>
    </LocaleProvider>
  )
}
