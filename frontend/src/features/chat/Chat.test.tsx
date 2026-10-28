import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../../app/App'
import { ApiError, postChat, postFeedback, type ChatResponse } from '../../services/api'

vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  postChat: vi.fn(),
  postFeedback: vi.fn(),
}))

const mockedPostChat = vi.mocked(postChat)
const mockedPostFeedback = vi.mocked(postFeedback)

const reply = (answer: string, extra: Partial<ChatResponse> = {}): ChatResponse => ({
  answer,
  refused: false,
  section: null,
  message_id: '3f2b1c9e-0000-4000-8000-000000000001',
  request_id: 'req-1',
  ...extra,
})

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Pregúntale a mi asistente' }))
  // The panel is a lazy chunk: the first load of it can be slow on a busy machine.
  return screen.findByRole('dialog', { name: 'Asistente de Johan' }, { timeout: 5000 })
}

beforeEach(() => {
  window.sessionStorage.clear()
  mockedPostChat.mockReset()
  mockedPostFeedback.mockReset()
  mockedPostFeedback.mockResolvedValue(undefined)
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
    mockedPostChat.mockResolvedValue(
      reply('Tiene 11 endpoints. Más en https://github.com/Joalregra', { section: 'projects' }),
    )
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
    mockedPostChat.mockResolvedValueOnce(reply('Ya funciona.'))
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

  it('shows the question limit message with the email and no retry for question_limit', async () => {
    mockedPostChat.mockRejectedValue(new ApiError(429, 'limit', 'question_limit'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Llegaste al límite de preguntas al asistente por ahora.')
    expect(alert).toHaveTextContent('Las preguntas rápidas siguen funcionando')
    expect(within(alert).getByRole('link', { name: 'johanalexis808@gmail.com' })).toHaveAttribute(
      'href',
      'mailto:johanalexis808@gmail.com',
    )
    expect(within(alert).queryByRole('button', { name: 'Reintentar' })).toBeNull()
    // the quick questions stay available
    expect(screen.getAllByRole('button', { name: /disponibilidad/i }).length).toBeGreaterThan(0)
  })

  it('keeps the generic rate limit message for a 429 without the question_limit code', async () => {
    mockedPostChat.mockRejectedValue(new ApiError(429, 'slow down', 'rate_limited'))
    const user = userEvent.setup()
    render(<App initialLocale="en" />)
    await user.click(screen.getByRole('button', { name: 'Ask my assistant' }))
    await screen.findByRole('dialog', {}, { timeout: 5000 })
    await user.type(screen.getByLabelText('Your question for the assistant'), 'Hi{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Wait a minute and try again.')
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
    mockedPostChat.mockResolvedValue(reply('Tres proyectos.'))
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
      quick: 'projects',
    })
    // The backend answers a button without calling a model, so it needs to know which one.
    expect(mockedPostChat).toHaveBeenCalledWith(
      expect.objectContaining({ quick_question_id: 'projects' }),
      expect.anything(),
    )

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
    mockedPostChat.mockResolvedValue(reply('Respuesta del proyecto.'))
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
    // A free-text question from a project card is not a quick question.
    expect(mockedPostChat.mock.calls[0][0].quick_question_id).toBeUndefined()
  })

  it('sends at most six earlier messages', async () => {
    mockedPostChat.mockResolvedValue(reply('ok'))
    window.sessionStorage.setItem(
      'chat:v1',
      JSON.stringify(
        Array.from({ length: 10 }, (_, index) => ({
          id: `m${index}`,
          role: index % 2 === 0 ? 'user' : 'assistant',
          content: `mensaje ${index}`,
        })),
      ),
    )
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)

    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'otra{Enter}')

    await waitFor(() => expect(mockedPostChat).toHaveBeenCalled())
    const { history } = mockedPostChat.mock.calls[0][0]
    expect(history).toHaveLength(6)
    expect(history[0].content).toBe('mensaje 4')
  })

  it('shows one link to the section the answer is based on, and none without a section', async () => {
    mockedPostChat.mockResolvedValueOnce(reply('Con enlace.', { section: 'skills' }))
    mockedPostChat.mockResolvedValueOnce(reply('Sin enlace.'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    const dialog = await openPanel(user)
    const input = screen.getByLabelText('Tu pregunta para el asistente')

    await user.type(input, 'uno{Enter}')
    expect(await screen.findByText('Con enlace.')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Habilidades' })).toHaveAttribute(
      'href',
      '#skills',
    )

    await user.type(input, 'dos{Enter}')
    expect(await screen.findByText('Sin enlace.')).toBeInTheDocument()
    expect(within(dialog).getAllByRole('link', { name: 'Habilidades' })).toHaveLength(1)
  })

  it('rates an answer once and keeps the rating after a reload', async () => {
    mockedPostChat.mockResolvedValue(reply('Respuesta útil.'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')
    await screen.findByText('Respuesta útil.')

    await user.click(screen.getByRole('button', { name: 'Me sirvió' }))

    expect(mockedPostFeedback).toHaveBeenCalledWith({
      message_id: '3f2b1c9e-0000-4000-8000-000000000001',
      helpful: true,
      locale: 'es',
    })
    expect(await screen.findByText('Gracias por tu opinión.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Me sirvió' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Me sirvió' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'No me sirvió' })).toBeDisabled()
    const saved = JSON.parse(window.sessionStorage.getItem('chat:v1') ?? '[]')
    expect(saved[1]).toMatchObject({ role: 'assistant', rating: 'up' })
  })

  it('sends a negative rating with helpful false', async () => {
    mockedPostChat.mockResolvedValue(reply('Respuesta floja.'))
    const user = userEvent.setup()
    render(<App initialLocale="en" />)
    await user.click(screen.getByRole('button', { name: 'Ask my assistant' }))
    await screen.findByRole('dialog', {}, { timeout: 5000 })
    await user.type(screen.getByLabelText('Your question for the assistant'), 'Hi{Enter}')
    await screen.findByText('Respuesta floja.')

    await user.click(screen.getByRole('button', { name: 'Not helpful' }))

    expect(mockedPostFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ helpful: false, locale: 'en' }),
    )
    expect(await screen.findByText('Thanks for your feedback.')).toBeInTheDocument()
  })

  it('lets the visitor try again when the rating could not be sent', async () => {
    mockedPostChat.mockResolvedValue(reply('Respuesta.'))
    mockedPostFeedback.mockRejectedValueOnce(new ApiError(503, 'down', 'feedback_unavailable'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')
    await screen.findByText('Respuesta.')

    await user.click(screen.getByRole('button', { name: 'Me sirvió' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Me sirvió' })).toBeEnabled())
    expect(screen.queryByText('Gracias por tu opinión.')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Me sirvió' }))
    expect(await screen.findByText('Gracias por tu opinión.')).toBeInTheDocument()
    expect(mockedPostFeedback).toHaveBeenCalledTimes(2)
  })

  it('keeps the rating when the backend never stored the answer (404)', async () => {
    mockedPostChat.mockResolvedValue(reply('Respuesta.'))
    mockedPostFeedback.mockRejectedValue(new ApiError(404, 'gone', 'not_found'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)
    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')
    await screen.findByText('Respuesta.')

    await user.click(screen.getByRole('button', { name: 'No me sirvió' }))

    expect(await screen.findByText('Gracias por tu opinión.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No me sirvió' })).toBeDisabled()
    expect(mockedPostFeedback).toHaveBeenCalledTimes(1)
  })

  it('offers no rating for the visitor questions or for answers saved without an id', async () => {
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
    expect(screen.queryByRole('group', { name: '¿Te sirvió esta respuesta?' })).toBeNull()
  })

  it('treats a paused assistant like an unavailable one, with the email', async () => {
    mockedPostChat.mockRejectedValue(new ApiError(503, 'paused', 'assistant_paused'))
    const user = userEvent.setup()
    render(<App initialLocale="es" />)
    await openPanel(user)

    await user.type(screen.getByLabelText('Tu pregunta para el asistente'), 'Hola{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('El asistente no está disponible')
  })
})
