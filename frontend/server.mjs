/** Same-origin production gateway: service credentials stay on the server. */
import { createServer } from 'node:http'
import { readFileSync } from 'node:fs'
import { readFile, realpath, stat } from 'node:fs/promises'
import { dirname, extname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
function envValue(name) {
  if (process.env[name]) return process.env[name]
  for (const file of [resolve(root, '.env.local'), resolve(root, '../backend/.env')]) {
    try {
      const line = readFileSync(file, 'utf8').split('\n').find((row) => row.startsWith(`${name}=`))
      if (line) return line.slice(name.length + 1).trim().replace(/^["']|["']$/g, '')
    } catch {}
  }
  return ''
}
const token = envValue('GASWISE_API_TOKEN')
const upstream = new URL(process.env.GASWISE_API_URL || 'http://127.0.0.1:8000')
if (!['http:', 'https:'].includes(upstream.protocol) || upstream.username || upstream.password) throw new Error('Invalid GASWISE_API_URL')
const dist = await realpath(resolve(root, 'dist'))
const allowed = new Set(['/v1/prices/history', '/v1/locations/resolve', '/v1/smart/search', '/v1/smart/rerank', '/v1/smart/routes', '/v1/smart/refresh-prices', '/v1/vehicles/resolve', '/v1/vehicles/vin', '/v1/vehicles/plate', '/v1/parts/fitment', '/v1/parts/search'])
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.xml': 'application/xml; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.ico': 'image/x-icon' }
const limits = new Map()
const windowMs = 60000
function json(response, status, detail) {
  response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
  response.end(JSON.stringify({ detail }))
}
const server = createServer(async (request, response) => {
  response.setHeader('X-Content-Type-Options', 'nosniff')
  response.setHeader('Referrer-Policy', 'no-referrer')
  response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self' https://cloudflareinsights.com; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'")
  try {
    const url = new URL(request.url || '/', 'http://localhost')
    if (url.pathname.startsWith('/api/')) {
      const path = url.pathname.slice(4)
      if (!allowed.has(path) || url.search) return json(response, 404, 'not_found')
      if (request.method !== 'POST') return json(response, 405, 'method_not_allowed')
      // Reject cross-origin browser submissions before attaching privileged credentials.
      if (request.headers.origin) {
        const origin = new URL(request.headers.origin)
        if (origin.host !== request.headers.host) return json(response, 403, 'origin_not_allowed')
      }
      if (request.headers['sec-fetch-site'] === 'cross-site') return json(response, 403, 'origin_not_allowed')
      if (!request.headers['content-type']?.startsWith('application/json')) return json(response, 415, 'json_required')
      const now = Date.now()
      for (const [key, value] of limits) if (value.until <= now) limits.delete(key)
      const key = request.socket.remoteAddress || 'local'
      const rate = limits.get(key) ?? { count: 0, until: now + windowMs }
      if (rate.count >= 30 || limits.size > 10000) { response.setHeader('Retry-After', Math.max(1, Math.ceil((rate.until - now) / 1000))); return json(response, 429, 'gateway_rate_limit') }
      rate.count++; limits.set(key, rate)
      const chunks = []
      let size = 0
      for await (const chunk of request) {
        size += chunk.length
        if (size > 1024 * 1024) return json(response, 413, 'request_too_large')
        chunks.push(chunk)
      }
      const body = Buffer.concat(chunks)
      try { JSON.parse(body.toString()) } catch { return json(response, 400, 'invalid_request') }
      const result = await fetch(new URL(path, upstream), {
        method: 'POST', body,
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        redirect: 'error', signal: AbortSignal.timeout(120000),
      })
      response.setHeader('Cache-Control', 'no-store')
      response.setHeader('Content-Type', 'application/json')
      const retry = result.headers.get('Retry-After')
      if (retry) response.setHeader('Retry-After', retry)
      response.writeHead(result.status)
      response.end(Buffer.from(await result.arrayBuffer()))
      return
    }
    if (request.method !== 'GET' && request.method !== 'HEAD') return json(response, 405, 'method_not_allowed')
    const pathname = decodeURIComponent(url.pathname)
    const path = resolve(dist, `.${pathname === '/' ? '/index.html' : pathname}`)
    if (path !== dist && !path.startsWith(dist + sep)) return json(response, 404, 'not_found')
    const file = await realpath(path)
    if (!file.startsWith(dist + sep) || !(await stat(file)).isFile()) return json(response, 404, 'not_found')
    response.setHeader('Content-Type', mime[extname(file)] || 'application/octet-stream')
    response.setHeader('Cache-Control', file.includes(`${sep}assets${sep}`) ? 'public, max-age=31536000, immutable' : 'no-cache')
    response.end(request.method === 'HEAD' ? undefined : await readFile(file))
  } catch (error) {
    json(response, error?.code === 'ENOENT' ? 404 : 502, error?.code === 'ENOENT' ? 'not_found' : 'gateway_unavailable')
  }
})
server.requestTimeout = 130000
server.headersTimeout = 15000
server.listen(Number(process.env.PORT || 4173), process.env.HOST || '127.0.0.1', () => {
  console.log(`GasWise production gateway listening on port ${process.env.PORT || 4173}`)
})

export { server }
