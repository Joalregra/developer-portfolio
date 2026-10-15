// Writes the rendered page into dist/es/index.html and dist/en/index.html, so the content is in
// the HTML itself (crawlers, link previews, first paint) and React hydrates it on load.
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const serverEntry = resolve('node_modules/.cache/ssr/entry-server.js')
const { render } = await import(pathToFileURL(serverEntry).href)
const placeholder = '<div id="root"></div>'

for (const locale of ['es', 'en']) {
  const file = resolve(`dist/${locale}/index.html`)
  const html = readFileSync(file, 'utf8')
  if (!html.includes(placeholder)) throw new Error(`${file} has no empty root to fill`)
  writeFileSync(file, html.replace(placeholder, `<div id="root">${render(locale)}</div>`))
  console.log(`prerendered dist/${locale}/index.html`)
}
