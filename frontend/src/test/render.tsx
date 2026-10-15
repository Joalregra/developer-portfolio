import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import type { Locale } from '../data/profile'
import { ChatProvider } from '../features/chat/ChatProvider'
import { LocaleProvider } from '../i18n/LocaleProvider'

/** Renders UI inside the same providers the app uses, in a fixed language. */
export function renderWithProviders(ui: ReactElement, locale: Locale = 'es') {
  return render(
    <LocaleProvider initialLocale={locale}>
      <ChatProvider>{ui}</ChatProvider>
    </LocaleProvider>,
  )
}
