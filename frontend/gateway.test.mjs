import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { once } from 'node:events'
import { after, test } from 'node:test'

let calls = 0
const upstream = createServer(async (request, response) => {
  calls++
  assert.equal(request.headers.authorization, 'Bearer gateway-test-token')
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  const body = JSON.parse(Buffer.concat(chunks).toString())
  response.setHeader('Content-Type', 'application/json')
  response.end(JSON.stringify({ echoed: body }))
})
upstream.listen(0, '127.0.0.1')
await once(upstream, 'listening')
process.env.PORT = '0'
process.env.GASWISE_API_URL = `http://127.0.0.1:${upstream.address().port}`
process.env.GASWISE_API_TOKEN = 'gateway-test-token'
const { server } = await import('./server.mjs')
if (!server.listening) await once(server, 'listening')
const base = `http://127.0.0.1:${server.address().port}`
after(async () => { await Promise.all([new Promise((resolve) => server.close(resolve)), new Promise((resolve) => upstream.close(resolve))]) })

test('serves the built app without service credentials', async () => {
  const result = await fetch(base)
  assert.equal(result.status, 200)
  assert.match(result.headers.get('content-type'), /text\/html/)
  assert.ok(!(await result.text()).includes('gateway-test-token'))
  const csp = result.headers.get('content-security-policy')
  assert.match(csp, /script-src 'self' https:\/\/static.cloudflareinsights.com;/)
  assert.match(csp, /connect-src 'self' https:\/\/cloudflareinsights.com;/)
  assert.doesNotMatch(csp, /unsafe-eval|script-src[^;]*unsafe-inline/)
})
test('injects server authentication and strips browser authorization', async () => {
  const result = await fetch(`${base}/api/v1/vehicles/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer browser-value' }, body: JSON.stringify({ text: 'test car' }) })
  assert.equal(result.status, 200)
  assert.deepEqual(await result.json(), { echoed: { text: 'test car' } })
  assert.equal(result.headers.get('cache-control'), 'no-store')
})
test('proxies the bounded history reader with server authentication', async () => {
  const body = { source: 'waze', station_id: 'one', fuel_type: 'regular', days: 30 }
  const response = await fetch(`${base}/api/v1/prices/history`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), { echoed: body })
})
test('rejects cross-origin credential use without upstream traffic', async () => {
  const previous = calls
  const result = await fetch(`${base}/api/v1/smart/search`, { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: 'https://untrusted.example' }, body: '{}' })
  assert.equal(result.status, 403)
  assert.equal(calls, previous)
})
test('only proxies the supported app endpoints and JSON requests', async () => {
  assert.equal((await fetch(`${base}/api/v1/unknown`, { method: 'POST' })).status, 404)
  assert.equal((await fetch(`${base}/api/v1/smart/search`)).status, 405)
  assert.equal((await fetch(`${base}/api/v1/smart/search`, { method: 'POST', body: '{}' })).status, 415)
})
test('cannot read files outside the static build', async () => {
  const result = await fetch(`${base}/%2e%2e%2fbackend%2f.env`)
  assert.equal(result.status, 404)
  assert.equal((await result.json()).detail, 'not_found')
})
test('enforces the gateway rate limit', async () => {
  let result
  for (let count = 0; count < 30; count++) result = await fetch(`${base}/api/v1/vehicles/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
  assert.equal(result.status, 429)
  assert.ok(Number(result.headers.get('retry-after')) > 0)
})
