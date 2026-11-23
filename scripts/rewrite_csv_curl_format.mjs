import fs from 'node:fs'

const file = 'admin-panel-apis.csv'
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
const quote = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`
const rows = parseCsv(fs.readFileSync(file, 'utf8'))
const header = rows.shift()
const endpoint = header.indexOf('Endpoint')
const curl = header.indexOf('cURL command')
for (const row of rows) {
  const url = `http://192.168.0.122:9000${row[endpoint]}`
  row[curl] = `curl --location '${url}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'`
}
fs.writeFileSync(file, [header, ...rows].map((r) => r.map(quote).join(',')).join('\n') + '\n', 'utf8')
console.log(`Reformatted ${rows.length} cURL commands.`)
