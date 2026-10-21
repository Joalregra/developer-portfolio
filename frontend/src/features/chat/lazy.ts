import { lazy } from 'react'

/** The panel code is only fetched when the chat is opened or the hero field gets focus (CHAT-09). */
export const loadChatPanel = () => import('./ChatPanel')
export const ChatPanel = lazy(loadChatPanel)
