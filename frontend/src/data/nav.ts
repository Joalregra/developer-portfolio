// Anchor ids are the same in both languages, so switching language keeps the position (IA-02).
export const NAV_SECTIONS = [
  'projects',
  'experience',
  'about',
  'skills',
  'education',
  'contact',
] as const
export type NavSection = (typeof NAV_SECTIONS)[number]
