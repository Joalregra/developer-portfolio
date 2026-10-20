import { expect, test, type Locator, type Page } from '@playwright/test'

// Phones from the smallest supported width up to a desktop, in both languages and both themes.
const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 640 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1024, height: 768 },
  { width: 1440, height: 900 },
] as const
const locales = ['es', 'en'] as const
const themes = ['light', 'dark'] as const

type Viewport = (typeof viewports)[number]

// Accessible names of the Gedocs image viewer, per language (see src/i18n).
const viewer = {
  es: {
    open: /^Ampliar imagen/,
    close: 'Cerrar la vista ampliada',
    previous: 'Imagen anterior',
    next: 'Imagen siguiente',
  },
  en: {
    open: /^Enlarge image/,
    close: 'Close the enlarged view',
    previous: 'Previous image',
    next: 'Next image',
  },
} as const

async function horizontalOverflow(page: Page) {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
}

/** Fails when any part of the element sits outside the viewport. */
async function expectInsideViewport(target: Locator, viewport: Viewport) {
  const box = await target.first().boundingBox()
  expect(box, 'the element is not rendered').not.toBeNull()
  if (!box) return
  expect(box.x).toBeGreaterThanOrEqual(-0.5)
  expect(box.y).toBeGreaterThanOrEqual(-0.5)
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 0.5)
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 0.5)
}

for (const viewport of viewports) {
  for (const locale of locales) {
    for (const theme of themes) {
      test.describe(`${locale} ${theme} ${viewport.width}x${viewport.height}`, () => {
        test.use({ viewport })

        test.beforeEach(async ({ page }) => {
          await page.addInitScript((value) => localStorage.setItem('theme', value), theme)
          await page.goto(`/${locale}/`)
        })

        test('has no horizontal scroll', async ({ page }) => {
          expect(await horizontalOverflow(page)).toBe(0)
        })

        test('shows the assistant field without scrolling', async ({ page }) => {
          await expectInsideViewport(page.locator('#hero-question'), viewport)
        })

        test('keeps the mobile menu inside the screen', async ({ page }) => {
          test.skip(viewport.width >= 1024, 'The menu is a bar from 1024 px')
          await page.locator('button[aria-controls="site-menu"]').click()
          const menu = page.locator('#site-menu')
          await expect(menu).toBeVisible()
          expect(await horizontalOverflow(page)).toBe(0)
          await expectInsideViewport(menu, viewport)
        })
      })
    }

    // The chat panel and the image viewer are checked in one theme: they do not depend on it.
    test.describe(`${locale} ${viewport.width}x${viewport.height} overlays`, () => {
      test.use({ viewport })

      test('opens the assistant panel fully inside the screen', async ({ page }) => {
        await page.goto(`/${locale}/`)
        await page.locator('#consult button[type="submit"]').click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 10_000 })
        await expectInsideViewport(dialog, viewport)
        await expectInsideViewport(dialog.getByRole('textbox'), viewport)
        expect(await horizontalOverflow(page)).toBe(0)
      })

      test('enlarges a Gedocs screenshot fully inside the screen', async ({ page }) => {
        const names = viewer[locale]
        await page.goto(`/${locale}/`)
        const opener = page.getByRole('button', { name: names.open }).first()
        await opener.scrollIntoViewIfNeeded()
        await opener.click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible()
        await expectInsideViewport(dialog.getByRole('img'), viewport)
        for (const name of [names.close, names.previous, names.next]) {
          await expectInsideViewport(dialog.getByRole('button', { name }), viewport)
        }
        expect(await horizontalOverflow(page)).toBe(0)
      })
    })
  }
}
