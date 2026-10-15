import type { Locale } from '../data/profile'

const monthFormatters = new Map<Locale, Intl.DateTimeFormat>()

function formatterFor(locale: Locale): Intl.DateTimeFormat {
  let formatter = monthFormatters.get(locale)
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(locale, {
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    })
    monthFormatters.set(locale, formatter)
  }
  return formatter
}

/** Formats an ISO month such as `2026-06` as "jun 2026" / "Jun 2026". */
export function formatMonth(isoMonth: string, locale: Locale): string {
  return formatterFor(locale).format(new Date(`${isoMonth}-01T00:00:00Z`))
}

export function formatMonthRange(start: string, end: string, locale: Locale): string {
  return `${formatMonth(start, locale)} – ${formatMonth(end, locale)}`
}

/** Formats an ISO month as a long label: "octubre de 2026" / "October 2026". */
export function formatLongMonth(isoMonth: string, locale: Locale): string {
  return new Intl.DateTimeFormat(locale, {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${isoMonth}-01T00:00:00Z`))
}
