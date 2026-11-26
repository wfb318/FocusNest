import { readFileSync } from 'node:fs'
import ts from 'typescript'
const cache = new Map()
export async function moduleUrl(url) {
  if (cache.has(url.href)) return cache.get(url.href)
  let code = ts.transpile(readFileSync(url, 'utf8'), { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 })
  for (const match of [...code.matchAll(/from ['"](\.[^'"]+)['"]/g)]) {
    const dependency = new URL(match[1] + (match[1].endsWith('.ts') ? '' : '.ts'), url)
    code = code.replace(match[0], `from ${JSON.stringify(await moduleUrl(dependency))}`)
  }
  const result = `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
  cache.set(url.href, result)
  return result
}
export async function loadTs(url) { return import(await moduleUrl(url)) }
