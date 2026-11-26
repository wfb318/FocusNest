import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

// Test the actual TypeScript renderer on the project's Node 20 without another runner.
const source = await readFile(new URL('../src/utils/markdown.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText.replace(/from ['"]markdown-it['"]/, `from ${JSON.stringify(import.meta.resolve('markdown-it'))}`)
const { renderMarkdown, renderJournalMarkdown } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('headings, lists, fenced code and emphasis render', () => {
  const html = renderMarkdown('# Today\n\n- **learn**\n\n```js\nconst x = 1\n```')
  assert.match(html, /<h1>Today<\/h1>/)
  assert.match(html, /<strong>learn<\/strong>/)
  assert.match(html, /<pre><code/)
})
test('raw HTML is escaped and images cannot make remote requests', () => {
  const html = renderMarkdown('<script>alert(1)</script>\n<img src="https://example.com/track">\n![image](https://example.com/track)')
  assert.doesNotMatch(html, /<script|<img|<iframe/i)
  assert.match(html, /&lt;script&gt;/)
})
test('dangerous links are blocked, ordinary links isolate their opener', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,evil', 'vbscript:evil']) {
    assert.doesNotMatch(renderMarkdown(`[link](${url})`), /<a\s/i)
  }
  const html = renderMarkdown('[docs](https://example.com)')
  assert.match(html, /target="_blank"/)
  assert.match(html, /rel="noopener noreferrer"/)
})

test('journal previews display URLs as text without navigation or external resources', () => {
  const html = renderJournalMarkdown([
    '# Private heading',
    '[link](https://example.invalid/?q=private)',
    '![image](https://example.invalid/attachment)',
    '<https://example.invalid/private>',
    '<img src="https://example.invalid/track">',
    '[reference][id]', '', '[id]: https://example.invalid/reference',
  ].join('\n'))
  assert.match(html, /<h1>Private heading<\/h1>/)
  assert.doesNotMatch(html, /<(a|img|iframe)\b|href=("|')https?:/i)
})
