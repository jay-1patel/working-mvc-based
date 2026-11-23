import fs from 'node:fs'

const file = 'admin-panel-apis.csv'
let text = fs.readFileSync(file, 'utf8')
text = text.replaceAll(' -H ""Authorization: Bearer YOUR_TOKEN""', ' -H ""username: YOUR_USERNAME"" -H ""session_id: YOUR_SESSION_ID""')
text = text.replaceAll(' -H ""Content-Type: application/json"" -d \'{}\'', ' -H ""Content-Type: application/json"" -d \'{"username":"YOUR_USERNAME","session_id":"YOUR_SESSION_ID"}\'')
fs.writeFileSync(file, text, 'utf8')
console.log('Updated CSV cURL authentication to username/session_id.')
