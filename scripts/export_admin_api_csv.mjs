import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const routesDir = path.join(root, 'backend', 'routes')
const rows = []
const methodRe = /@(router|flat_router)\.(get|post|put|patch|delete)\(([^\n]*)/g

const descriptions = (method, endpoint, tag) => {
  const clean = endpoint.replace(/\{[^}]+\}/g, 'value')
  const action = { get: 'Reads', post: 'Creates or runs', put: 'Updates', patch: 'Updates', delete: 'Deletes' }[method]
  return `${action} ${clean.split('?')[0].replaceAll('/', ' ').trim() || tag.toLowerCase()} data for the ${tag.toLowerCase()} page.`
}

const curl = (method, endpoint) => {
  const bodyMethods = new Set(['post', 'put', 'patch'])
  const body = bodyMethods.has(method) ? ` -H "Content-Type: application/json" -d '{}'` : ''
  return `curl -X ${method.toUpperCase()} "${'${BASE_URL}'}${endpoint}" -H "Authorization: Bearer ${'${TOKEN}'}"${body}`
}

for (const filename of fs.readdirSync(routesDir).filter((name) => name.endsWith('.py'))) {
  const source = fs.readFileSync(path.join(routesDir, filename), 'utf8')
  const prefixes = [...source.matchAll(/(?:router|flat_router)\s*=\s*APIRouter\(prefix\s*=\s*["']([^"']*)/g)].map((m) => m[1])
  const prefix = prefixes[0] || ''
  const tag = filename.replace(/\.py$/, '').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  for (const match of source.matchAll(methodRe)) {
    const method = match[2]
    let raw = match[3].match(/["']([^"']*)["']/)?.[1]
    if (!raw || raw.startsWith('http')) continue
    if (!raw.startsWith('/')) raw = `/${raw}`
    const endpoint = `${prefix}${raw}`.replace(/\/+/g, '/')
    // Keep customer/public runtime endpoints out; this file is for admin-panel APIs.
    if (!endpoint.startsWith('/api/admin') && !endpoint.startsWith('/api/auth') && !endpoint.startsWith('/api/tenants') && !endpoint.startsWith('/api/integration-requests') && !endpoint.startsWith('/api/tenant-change-requests')) continue
    rows.push({ tag, method: method.toUpperCase(), endpoint, curl: curl(method, endpoint), description: descriptions(method, endpoint, tag), source: `backend/routes/${filename}` })
  }
}

// Add the tenant-scoped aliases used by the console when the route module uses a flat router.
rows.sort((a, b) => a.tag.localeCompare(b.tag) || a.endpoint.localeCompare(b.endpoint) || a.method.localeCompare(b.method))
const header = ['Page / API tag', 'HTTP method', 'Endpoint', 'cURL command', 'Humanized description', 'Backend source']
const quote = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
const csv = [header, ...rows.map((row) => [row.tag, row.method, row.endpoint, row.curl, row.description, row.source])]
  .map((line) => line.map(quote).join(','))
  .join('\n') + '\n'

const output = path.join(root, 'admin-panel-apis.csv')
fs.writeFileSync(output, csv, 'utf8')
console.log(`Wrote ${rows.length} APIs to ${output}`)
