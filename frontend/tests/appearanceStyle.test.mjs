import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
const source = await readFile(new URL('../src/utils/appearanceStyle.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const { DEFAULT_STYLE, normalizeStyle, styleVariables } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('old preferences use compatible defaults and sizes stay in range', () => {
  assert.deepEqual(normalizeStyle(), DEFAULT_STYLE)
  assert.equal(normalizeStyle({ fontScale: 2 }).fontScale, 1.5)
  assert.equal(normalizeStyle({ fontScale: -1 }).fontScale, 0.8)
  assert.equal(normalizeStyle({ fontScale: NaN }).fontScale, 1)
})
test('colors only accept complete hex values', () => {
  assert.equal(normalizeStyle({ textColor: '#AABBCC' }).textColor, '#aabbcc')
  assert.equal(normalizeStyle({ glassColor: 'url(https://example.com)' }).glassColor, '#ffffff')
  assert.equal(normalizeStyle({ textColor: '#fff' }).textColor, '#263c34')
})
test('font scale and both colors produce consistent CSS variables', () => {
  const variables = styleVariables({ fontScale: 1.25, textColor: '#ffffff', glassColor: '#123456' })
  assert.equal(variables['--ui-font-scale'], '1.25')
  assert.equal(variables['--text-primary'], '#ffffff')
  assert.equal(variables['--glass-rgb'], '18,52,86')
  assert.equal(variables['--el-font-size-base'], 'calc(14px * 1.25)')
})
