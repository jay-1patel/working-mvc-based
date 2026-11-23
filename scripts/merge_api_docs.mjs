import fs from 'node:fs'

const sidebar = fs.readFileSync('sidebar-page-apis.md', 'utf8').trim()
const superadmin = fs.readFileSync('superadmin-apis.md', 'utf8').trim()
const merged = `# Admin panel API reference\n\n${sidebar.replace(/^# Sidebar page APIs \(curl\)/, '## Sidebar page APIs')}\n\n---\n\n${superadmin.replace(/^# Super-admin APIs/, '## Super-admin APIs')}\n`
fs.writeFileSync('admin-panel-apis-merged.md', merged, 'utf8')
console.log('Created admin-panel-apis-merged.md')
