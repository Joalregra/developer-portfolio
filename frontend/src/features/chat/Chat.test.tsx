import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../../app/App'
import { ApiError, postChat } from '../../services/api'

vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  postChat: vi.fn(),
}))

const mockedPostChat = vi.mocked(postChat)

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Pregúntale a mi asistente' }))
  // The panel is a lazy chunk: the first load of it can be slow on a busy machine.
  return screen.findByRole('dialog', { name: 'Asistente de Johan' }, { timeout: 5000 })
}

beforeEach(() => {
  window.sessionStorage.clear()
  mockedPostChat.mockReset()
})

afterEach(() => {
  window.history.replaceState(null, '', '/')
  Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
})

describe('chat assistant', () => {
  it('opens as a dialog with the focus in the text field, and closes with Escape', async () => {
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    const launcher = screen.getByRole('button', { name: 'Pregúntale a mi asistente' })
    expect(launcher).toHaveAttribute('aria-expanded', 'false')

    const dialog = await openPanel(user)
    expect(dialog).toBeInTheDocument()
    expect(screen.getByLabelText('Tu pregunta para el asistente')).toHaveFocus()
    expect(within(dialog).getByText(/Asistente con IA/)).toBeInTheDocument()
    expect(within(dialog).getByText(/se guardan de forma anónima/)).toBeInTheDocument()

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await waitFor(() => expect(launcher).toHaveFocus())
  })

  it('starts empty with six quick questions', async () => {
    const user = userEvent.setup()
    render(<App initialLocale="en" />)
    await user.click(screen.getByRole('button', { name: 'Ask my assistant' }))
    const dialog = await screen.findByRole('dialog', {}, { timeout: 5000 })
    expect(dialog).toHaveTextContent('Ask anything you want to know about Johan')
    expect(dialog.querySelectorAll('ul li button')).toHaveLength(6)
  })

  it('sends with Enter, shows the answer and the sources link', async () => {
    mockedPostChat.mockResolvedValue({
      answer: 'Tiene 11 endpoints. Más en https://github.com/Joalregra',
      sources: ['projects'],
    })
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    const dialog = await openPanel(user)

    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')

    expect(await screen.findByText(/Tiene 11 endpoints/)).toBeInTheDocument()
    expect(mockedPostChat).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Hola', locale: 'es', history: [] }),
      expect.anything(),
    )
    const log = screen.getByRole('log')
    expect(log).toHaveTextContent('Tú:')
    expect(log).toHaveTextContent('Asistente:')
    const link = within(dialog).getByRole('link', { name: 'https://github.com/Joalregra' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(within(dialog).getByRole('link', { name: 'Proyectos' })).toHaveAttribute(
      'href',
      '#projects',
    )
    expect(log).toHaveTextContent('Ver en:')
  })

  it('does not send on Shift+Enter', async () => {
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    const input = screen.getByLabelText('Tu pregunta para el asistente')
    await user.type(input, 'línea uno{Shift>}{Enter}{/Shift}línea dos')
    expect(mockedPostChat).not.toHaveBeenCalled()
    expect(input).toHaveValue('línea uno\nlínea dos')
  })

  it('shows the counter from 800 characters and blocks sending over 1000', async () => {
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    const input = screen.getByLabelText('Tu pregunta para el asistente')
    const send = screen.getByRole('button', { name: 'Enviar' })
    expect(send).toBeDisabled()

    await user.click(input)
    await user.paste('a'.repeat(799))
    expect(screen.queryByText(/de 1000 caracteres/)).toBeNull()
    expect(send).toBeEnabled()

    await user.paste('a')
    expect(screen.getByText('800 de 1000 caracteres')).toBeInTheDocument()

    await user.paste('a'.repeat(201))
    expect(screen.getByText('1001 de 1000 caracteres')).toBeInTheDocument()
    expect(send).toBeDisabled()
  })

  it('explains an unavailable assistant with the email and a retry that works', async () => {
    mockedPostChat.mockRejectedValueOnce(new ApiError(503, 'down'))
    mockedPostChat.mockResolvedValueOnce({ answer: 'Ya funciona.' })
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('El asistente no está disponible ahora. Puedes escribirme a')
    expect(within(alert).getByRole('link', { name: 'johanalexis808@gmail.com' })).toHaveAttribute(
      'href',
      'mailto:johanalexis808@gmail.com',
    )

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Ya funciona.')).toBeInTheDocument()
    expect(mockedPostChat).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows the rate limit message for a 429', async () => {
    mockedPostChat.mockRejectedValue(new ApiError(429, 'slow down'))
    const user = userEvent.setup()
    render(<App initialLocale="en" />)
    await user.click(screen.getByRole('button', { name: 'Ask my assistant' }))
    await screen.findByRole('dialog', {}, { timeout: 5000 })
    await user.type(screen.getByLabelText('Your question for the assistant'), 'Hi{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You have asked many questions in a row. Wait a minute and try again.',
    )
  })

  it('shows the offline message when there is no connection', async () => {
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
    mockedPostChat.mockRejectedValue(new TypeError('Failed to fetch'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión. Revisa tu internet.')
  })

  it('sends a quick question and keeps the conversation in sessionStorage', async () => {
    mockedPostChat.mockResolvedValue({ answer: 'Tres proyectos.' })
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    const dialog = await openPanel(user)
    await user.click(within(dialog).getByRole('button', { name: 'Proyectos más importantes' }))
    expect(await screen.findByText('Tres proyectos.')).toBeInTheDocument()

    const saved = JSON.parse(window.sessionStorage.getItem('chat:v1') ?? '[]')
    expect(saved).toHaveLength(2)
    expect(saved[0]).toMatchObject({
      role: 'user',
      content: '¿Cuáles son tus proyectos más importantes?',
    })

    await user.click(screen.getByRole('button', { name: 'Nueva conversación' }))
    expect(window.sessionStorage.getItem('chat:v1')).toBeNull()
    expect(screen.queryByText('Tres proyectos.')).toBeNull()
  })

  it('restores a saved conversation after a reload', async () => {
    window.sessionStorage.setItem(
      'chat:v1',
      JSON.stringify([
        { id: 'a', role: 'user', content: 'Pregunta guardada' },
        { id: 'b', role: 'assistant', content: 'Respuesta guardada' },
      ]),
    )
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    expect(screen.getByText('Respuesta guardada')).toBeInTheDocument()
  })

  it('opens with the question sent from a project', async () => {
    mockedPostChat.mockResolvedValue({ answer: 'Respuesta del proyecto.' })
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    const buttons = screen.getAllByRole('button', {
      name: 'Pregúntale al asistente sobre este proyecto',
    })
    await user.click(buttons[2])
    await screen.findByRole('dialog', {}, { timeout: 5000 })
    expect(mockedPostChat).toHaveBeenCalledWith(
      expect.objectContaining({ message: '¿Qué hizo Johan en Gedocs?' }),
      expect.anything(),
    )
    expect(await screen.findByText('Respuesta del proyecto.')).toBeInTheDocument()
  })
})
