import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import axios from 'axios'

const source = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
  .replace(/from ['"]axios['"]/, `from ${JSON.stringify(import.meta.resolve('axios'))}`)
  .replace('import.meta.env.VITE_API_BASE_URL', 'undefined')
const { apiClient, configureAuthTransport } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('a late response or 401 from a closed session is discarded without retry', async () => {
  let generation = 1, token = 'previous', refreshes = 0
  configureAuthTransport(() => token, async () => { refreshes++; return true }, () => generation)
  for (const status of [200, 401]) {
    let finish
    const response = apiClient.get('/journals/encrypted/today', {
      adapter: config => new Promise((resolve, reject) => {
        assert.equal(config.headers.get('Authorization'), `Bearer ${token}`)
        finish = () => {
          const response = { status, config, data: { data: 'synthetic private response' } }
          if (status === 200) resolve(response)
          else reject(new axios.AxiosError('expired', undefined, config, undefined, response))
        }
      }),
    })
    generation++
    token = 'replacement'
    finish()
    await assert.rejects(response, axios.isCancel)
  }
  assert.equal(refreshes, 0)
})

test('an expired request retries with a fresh token in the same session', async () => {
  let token = 'expired'
  configureAuthTransport(() => token, async () => { token = 'refreshed'; return true }, () => 1)
  const sent = []
  const result = await apiClient.get('/notes', {
    adapter: async config => {
      sent.push(config.headers.get('Authorization'))
      const response = { config, status: sent.length === 1 ? 401 : 200, data: 'test' }
      if (response.status === 401) throw new axios.AxiosError('expired', undefined, config, undefined, response)
      return response
    },
  })
  assert.equal(result.data, 'test')
  assert.deepEqual(sent, ['Bearer expired', 'Bearer refreshed'])
})
