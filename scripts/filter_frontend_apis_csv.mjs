import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const csvPath = path.join(root, 'admin-panel-apis.csv')
const frontend = path.join(root, 'frontend', 'src')

function parseCsv(text) {
  const records = []
  let row = [], cell = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted && ch === '"' && text[i + 1] === '"') { cell += '"'; i++; continue }
    if (ch === '"') { quoted = !quoted; continue }
    if (!quoted && ch === ',') { row.push(cell); cell = ''; continue }
    if (!quoted && ch === '\n') { row.push(cell.replace(/\r$/, '')); records.push(row); row = []; cell = ''; continue }
    cell += ch
  }
  if (cell || row.length) { row.push(cell); records.push(row) }
  return records
}

function csvCell(value) { return `"${String(value ?? '').replaceAll('"', '""')}"` }
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    return entry.isDirectory() ? files(full) : /\.(ts|tsx)$/.test(entry.name) ? [full] : []
  })
}

const source = files(frontend).map((file) => fs.readFileSync(file, 'utf8')).join('\n')
// Replace template expressions with a wildcard so tenant/user IDs still match.
const sourceRoutes = [...source.matchAll(/[`'\"](\/api\/[^`'\"\s$]*(?:\$\{[^}]+\}[^`'\"\s]*)?)[`'\"]/g)]
  .map((m) => m[1].replace(/\$\{[^}]+\}/g, '*'))

const routePattern = (route) => new RegExp(`^${route.split('*').map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*')}$`)
const records = parseCsv(fs.readFileSync(csvPath, 'utf8'))
const header = records.shift()
const endpointIndex = header.indexOf('Endpoint')
const methodIndex = header.indexOf('HTTP method')
const curlIndex = header.indexOf('cURL command')
const kept = records.filter((row) => {
  const endpoint = row[endpointIndex]
  const candidate = endpoint.replace(/\{[^}]+\}/g, '*')
  return sourceRoutes.some((route) => routePattern(route).test(candidate) || routePattern(candidate).test(route))
}).map((row) => {
  row[methodIndex] = 'POST'
  row[curlIndex] = row[curlIndex]
    .replace(/-X\s+(GET|PUT|PATCH|DELETE|POST)/i, '-X POST')
    .replace(/ -H "Content-Type: application\/json" -d '\{\}'$/, '')
  if (!row[curlIndex].includes('Content-Type: application/json')) row[curlIndex] += ' -H "Content-Type: application/json" -d \'{}\''
  return row
})

const output = [header, ...kept].map((row) => row.map(csvCell).join(',')).join('\n') + '\n'
fs.writeFileSync(csvPath, output, 'utf8')
console.log(`Kept ${kept.length} frontend-used APIs and converted all to POST.`)
