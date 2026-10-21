// Writes dist/_headers: the security headers Cloudflare adds to every response of the site.
//
// It runs at the end of `npm run build`, after the pages are prerendered, because the
// Content-Security-Policy needs two things only the build knows:
//   - the SHA-256 of every inline script and style the pages carry (the theme script in <head>
//     and the style block of 404.html), so the policy needs no 'unsafe-inline' for scripts;
//   - the origin of the API (VITE_API_URL), which is the only other place the browser may call.
// Neither is written by hand: a hand-written hash breaks the day Prettier reformats the script,
// and a hand-written API address would put the real domain in the repository.
import { createHash } from 'node:crypto'
import { readdir, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { loadEnv } from 'vite'

// A <script> with one of these types runs. Anything else (JSON-LD) is data and the policy does
// not apply to it.
const EXECUTABLE_SCRIPT_TYPES = new Set(['', 'module', 'text/javascript', 'application/javascript'])

/**
 * CSP source for an inline block: 'sha256-<base64 of the text between the tags>'.
 *
 * The browser hashes the text after its HTML parser turned every CRLF and lone CR into LF. A page
 * built on Windows has CRLF on disk, so hashing the file as it is would give a hash the browser
 * never computes, and it would block the script.
 */
export function hashOf(text) {
  const parsed = text.replace(/\r\n?/g, '\n')
  return `'sha256-${createHash('sha256').update(parsed, 'utf8').digest('base64')}'`
}

/** The inline scripts that run, and the inline styles, of one HTML page (text between the tags). */
export function inlineBlocks(html) {
  const scripts = []
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const [, attributes, text] = match
    if (/\bsrc\s*=/i.test(attributes) || text.trim() === '') continue
    const type = /\btype\s*=\s*["']?([^"'\s>]+)/i.exec(attributes)?.[1] ?? ''
    if (EXECUTABLE_SCRIPT_TYPES.has(type.toLowerCase())) scripts.push(text)
  }
  const styles = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map((match) => match[1])
  return { scripts, styles }
}

/** "https://api.yourdomain.com/" -> "https://api.yourdomain.com". Empty input gives null. */
export function originOf(url) {
  if (!url) return null
  try {
    return new URL(url).origin
  } catch {
    throw new Error(`VITE_API_URL is not a valid URL: ${url}`)
  }
}

export function buildCsp({ scriptHashes, styleHashes, apiOrigin }) {
  const join = (...sources) => sources.filter(Boolean).join(' ')
  return [
    "default-src 'self'",
    `script-src ${join("'self'", ...scriptHashes)}`,
    `style-src ${join("'self'", ...styleHashes)}`,
    "img-src 'self'",
    "font-src 'self'",
    `connect-src ${join("'self'", apiOrigin)}`,
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ')
}

/** The text of the _headers file. */
export function renderHeaders(csp) {
  return `${[
    '/*',
    '  X-Content-Type-Options: nosniff',
    '  Referrer-Policy: strict-origin-when-cross-origin',
    '  X-Frame-Options: DENY',
    '  Permissions-Policy: camera=(), microphone=(), geolocation=()',
    '  Strict-Transport-Security: max-age=31536000',
    `  Content-Security-Policy: ${csp}`,
    '',
    // Vite names these files after their content, so they never change under the same name.
    '/assets/*',
    '  Cache-Control: public, max-age=31536000, immutable',
  ].join('\n')}\n`
}

async function htmlFiles(directory) {
  const files = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...(await htmlFiles(path)))
    else if (entry.name.endsWith('.html')) files.push(path)
  }
  return files
}

async function main() {
  const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
  const dist = join(root, 'dist')
  // The same .env files and VITE_ variables Vite used for this build.
  const apiOrigin = originOf(loadEnv('production', root, 'VITE_').VITE_API_URL)
  const onCloudflare = process.env.WORKERS_CI || process.env.CF_PAGES || process.env.REQUIRE_API_URL
  if (!apiOrigin && onCloudflare) {
    throw new Error('VITE_API_URL is not set: set it in the Cloudflare build variables.')
  }
  if (!apiOrigin) {
    console.warn('security-headers: VITE_API_URL is not set, so connect-src allows only the site.')
  }

  const scriptHashes = new Set()
  const styleHashes = new Set()
  const pages = await htmlFiles(dist)
  for (const page of pages) {
    const { scripts, styles } = inlineBlocks(await readFile(page, 'utf8'))
    for (const text of scripts) scriptHashes.add(hashOf(text))
    for (const text of styles) styleHashes.add(hashOf(text))
  }

  const csp = buildCsp({
    scriptHashes: [...scriptHashes].sort(),
    styleHashes: [...styleHashes].sort(),
    apiOrigin,
  })
  await writeFile(join(dist, '_headers'), renderHeaders(csp), 'utf8')
  console.log(
    `security-headers: dist/_headers written (${pages.length} pages, ` +
      `${scriptHashes.size} script and ${styleHashes.size} style hashes, API ${apiOrigin ?? 'none'})`,
  )
}

// Run only when started as a script, so the tests can import the functions above.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.message)
    process.exit(1)
  })
}
