import fs from 'node:fs'

const csvFile = 'admin-panel-apis.csv'
const mdFile = 'admin-panel-apis.md'

function parseCsv(text) {
  const out = []; let row = []; let cell = ''; let quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted && ch === '"' && text[i + 1] === '"') { cell += '"'; i++; continue }
    if (ch === '"') { quoted = !quoted; continue }
    if (!quoted && ch === ',') { row.push(cell); cell = ''; continue }
    if (!quoted && ch === '\n') { row.push(cell.replace(/\r$/, '')); out.push(row); row = []; cell = ''; continue }
    cell += ch
  }
  if (cell || row.length) { row.push(cell); out.push(row) }
  return out
}

const records = parseCsv(fs.readFileSync(csvFile, 'utf8'))
const header = records.shift()
const index = Object.fromEntries(header.map((name, i) => [name, i]))
const grouped = new Map()
for (const row of records) {
  const tag = row[index['Page / API tag']]
  if (!grouped.has(tag)) grouped.set(tag, [])
  grouped.get(tag).push({
    method: row[index['HTTP method']],
    endpoint: row[index.Endpoint],
    curl: row[index['cURL command']],
    description: row[index['Humanized description']],
  })
}

let md = '# Admin panel API reference\n\n'
md += 'Base URL: `http://192.168.0.122:9000`  \n'
md += 'Authentication: every request uses the `username` and `session_id` headers and JSON fields.  \n'
md += 'Scope: APIs currently referenced by the frontend admin panel. All entries below use `POST` as configured.\n\n'
md += `Total APIs: **${records.length}**\n\n`
md += '> Replace the sample username and session ID with the active credentials for the account making the request.\n\n'

for (const [tag, apis] of grouped) {
  md += `## ${tag}\n\n`
  for (const api of apis) {
    md += `### ${api.method} ${api.endpoint}\n\n`
    md += `${api.description}\n\n`
    md += '```bash\n' + api.curl + '\n```\n\n'
  }
}

fs.writeFileSync(mdFile, md, 'utf8')
console.log(`Wrote ${records.length} APIs to ${mdFile}`)
