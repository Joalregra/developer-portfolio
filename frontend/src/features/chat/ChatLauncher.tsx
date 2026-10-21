import { useEffect, useState } from 'react'
import { ChatIcon } from '../../components/ui/icons'
import { useLocale } from '../../hooks/useLocale'
import { useChatContext } from './ChatContext'
import { loadChatPanel } from './lazy'

export const PANEL_ID = 'assistant-panel'

/** True while the hero's own assistant block is on screen, so the two never overlap. */
function useHeroConsultVisible(): boolean {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const target = document.getElementById('consult')
    if (!target || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting))
    observer.observe(target)
    return () => observer.disconnect()
  }, [])

  return visible
}

export function ChatLauncher() {
  const { t } = useLocale()
  const { isOpen, openChat, closeChat, launcherRef } = useChatContext()
  const heroVisible = useHeroConsultVisible()
  const covered = heroVisible && !isOpen

  return (
    <button
      ref={launcherRef}
      type="button"
      data-print="hide"
      aria-expanded={isOpen}
      aria-controls={PANEL_ID}
      onPointerEnter={() => void loadChatPanel()}
      onFocus={() => void loadChatPanel()}
      onClick={() => (isOpen ? closeChat() : openChat())}
      className={`fixed right-4 bottom-4 z-40 min-h-12 items-center gap-2 rounded-lg bg-spot px-4 text-base font-semibold text-on-spot shadow-panel transition-[opacity,visibility,transform] duration-(--dur-base) hover:-translate-y-0.5 sm:right-6 sm:bottom-6 ${
        isOpen ? 'hidden sm:inline-flex' : 'inline-flex'
      } ${covered ? 'invisible opacity-0' : 'visible opacity-100'}`}
    >
      <ChatIcon />
      {/* Icon only on phones; the text stays in the accessible name (label matches what is seen). */}
      <span className="sr-only sm:not-sr-only">{t.chat.launcher}</span>
    </button>
  )
}
