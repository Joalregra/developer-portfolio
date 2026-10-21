import { describe, expect, it } from 'vitest'
import { buildCsp, hashOf, inlineBlocks, originOf, renderHeaders } from './security-headers.mjs'

const THEME_SCRIPT = `
        try {
          var theme = localStorage.getItem('theme')
          if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme
        } catch (error) {}
      `

const PAGE = `<!doctype html><html><head>
  <script>${THEME_SCRIPT}</script>
  <script type="application/ld+json">{"@type":"Person"}</script>
  <script type="module" crossorigin src="/assets/main-abc.js"></script>
  <style>body{margin:0}</style>
  <link rel="stylesheet" href="/assets/main.css">
</head><body><div id="root"></div></body></html>`

describe('inlineBlocks', () => {
  it('finds the inline script that runs and the inline style', () => {
    const { scripts, styles } = inlineBlocks(PAGE)

    expect(scripts).toEqual([THEME_SCRIPT])
    expect(styles).toEqual(['body{margin:0}'])
  })

  it('ignores external scripts, empty scripts and JSON-LD data blocks', () => {
    const html =
      '<script src="/a.js"></script><script> </script><script type="application/ld+json">{}</script>'

    expect(inlineBlocks(html)).toEqual({ scripts: [], styles: [] })
  })
})

describe('hashOf', () => {
  it('is the base64 SHA-256 of the exact text, as the browser computes it', () => {
    // SHA-256("abc") is a published test vector.
    expect(hashOf('abc')).toBe("'sha256-ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0='")
  })

  it('hashes a line break as the browser does, so a Windows build gives the same hash', () => {
    expect(hashOf('a\r\nb\rc\nd')).toBe(hashOf('a\nb\nc\nd'))
  })

  it('changes with a single character, such as a different indentation', () => {
    expect(hashOf(' x')).not.toBe(hashOf('x'))
  })
})

describe('originOf', () => {
  it('keeps only the origin of the API address', () => {
    expect(originOf('https://api.yourdomain.com/')).toBe('https://api.yourdomain.com')
    expect(originOf('https://api.yourdomain.com/api/chat')).toBe('https://api.yourdomain.com')
  })

  it('returns null when there is no address, and refuses one that is not a URL', () => {
    expect(originOf('')).toBeNull()
    expect(originOf(undefined)).toBeNull()
    expect(() => originOf('api.yourdomain.com')).toThrow(/not a valid URL/)
  })
})

describe('buildCsp', () => {
  const csp = buildCsp({
    scriptHashes: ["'sha256-aaa'"],
    styleHashes: ["'sha256-bbb'"],
    apiOrigin: 'https://api.yourdomain.com',
  })

  it('allows inline code only through hashes', () => {
    expect(csp).toContain("script-src 'self' 'sha256-aaa'")
    expect(csp).toContain("style-src 'self' 'sha256-bbb'")
    expect(csp).not.toContain('unsafe-inline')
    expect(csp).not.toContain('unsafe-eval')
  })

  it('lets the page call only itself and the API', () => {
    expect(csp).toContain("connect-src 'self' https://api.yourdomain.com;")
  })

  it('forbids plugins, framing and a changed base address', () => {
    expect(csp).toContain("object-src 'none'")
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("base-uri 'self'")
  })

  it('allows only the site when there is no API address', () => {
    const local = buildCsp({ scriptHashes: [], styleHashes: [], apiOrigin: null })

    expect(local).toContain("connect-src 'self';")
    expect(local).toContain("script-src 'self';")
  })
})

describe('renderHeaders', () => {
  it('writes one block for every path and a long cache only for the hashed assets', () => {
    const text = renderHeaders("default-src 'self'")

    expect(text.startsWith('/*\n')).toBe(true)
    expect(text).toContain("  Content-Security-Policy: default-src 'self'\n")
    expect(text).toContain('  X-Content-Type-Options: nosniff\n')
    expect(text).toContain('/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n')
    expect(text.endsWith('\n')).toBe(true)
  })
})
