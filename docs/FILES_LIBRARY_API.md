

## List uploaded files

UI: open a module chip (FAQ / Knowledge base / Brochure / New releases) and optional search.

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"module":"kb","search":""}'
```

Other modules:

```bash
# FAQ
--data '{"module":"faq","search":""}'

# Brochure (UI label) → catalogue
--data '{"module":"catalogue","search":""}'

# New releases (UI label) → new_arrival
--data '{"module":"new_arrival","search":""}'
```

---

## Upload a knowledge-base document

UI: select **Knowledge base** chip → **Upload to Knowledge base**

Replace `BASE64_FILE_CONTENT` with the document Base64 (no `data:...;base64,` prefix).

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/upload" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"knowledge.pdf","content":"BASE64_FILE_CONTENT","module":"kb","media_type":"application/pdf"}'
```

---

## Upload an FAQ document

UI: select **FAQ** chip → **Upload to FAQ**

Replace `BASE64_FILE_CONTENT` with real Base64 (see helper at the bottom).  
Sending the literal placeholder string fails Base64 decoding.

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/upload" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"faq.pdf","content":"BASE64_FILE_CONTENT","module":"faq","media_type":"application/pdf"}'
```

---

## Upload a brochure document

UI: select **Brochure** chip → **Upload to Brochure**  
Module value is `catalogue`.

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/upload" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"brochure.pdf","content":"BASE64_FILE_CONTENT","module":"catalogue","media_type":"application/pdf"}'
```

---

## Upload a new-releases document

UI: select **New releases** chip → **Upload to New releases**  
Module value is `new_arrival`.

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/upload" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"new-releases.pdf","content":"BASE64_FILE_CONTENT","module":"new_arrival","media_type":"application/pdf"}'
```

---

## Preview an uploaded file

UI: Eye icon on a file row

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/preview" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"knowledge.pdf"}' \
  --output preview.bin
```

---

## Download an uploaded file

UI: Download icon on a file row

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/download" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"knowledge.pdf"}' \
  --output knowledge.pdf
```

---

## Delete an uploaded file

UI: Trash icon on a file row

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/delete" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filename":"knowledge.pdf"}'
```

---

## Re-process existing files

UI: **Re-process library** (runs for filenames currently listed in the active module)

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/bifurcate-existing" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"filenames":["knowledge.pdf"],"auto_publish":false}'
```

---

## List knowledge gaps

UI: **Customer Knowledge Gaps & Unanswered Queries** panel under File library

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/knowledge-gaps" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"resolved":false,"limit":50}'
```

---

## Resolve a knowledge gap

UI: mark gap resolved

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/knowledge-gaps/resolve" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"gap_id":1,"notes":"Resolved"}'
```

---

## Create an FAQ from a knowledge gap

UI: create FAQ modal on a gap row

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/knowledge-gaps/create-faq" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"gap_id":1,"question":"Example question?","answer":"Example answer."}'
```

---

## List onboarding-kit templates

Not part of File library. Used by the onboarding / **Upload documents** flow.

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/onboarding-kits/list" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{}'
```

---

## Important: Base64 must be real file bytes

Leaving `"content":"BASE64_FILE_CONTENT"` causes:

`Invalid base64-encoded string: number of data characters (17) cannot be 1 more than a multiple of 4`

That used to surface as HTTP 500 (`req_9f07da27`). It now returns HTTP 400 with a clear message after the fix in `run_upload`.

### PowerShell (recommended on Windows)

```powershell
$sid = "YOUR_SESSION_ID"
$pdfPath = "C:\path\to\faq.pdf"
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($pdfPath))
$body = @{
  filename   = [IO.Path]::GetFileName($pdfPath)
  content    = $b64
  module     = "faq"
  media_type = "application/pdf"
} | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post `
  -Uri "http://10.100.100.43:9000/api/admin/tenants/files/upload" `
  -Headers @{ username = "cars"; session_id = $sid } `
  -ContentType "application/json" `
  -Body $body
```

### bash + curl

```bash
B64=$(base64 -w0 faq.pdf)
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/files/upload" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data "{\"filename\":\"faq.pdf\",\"content\":\"$B64\",\"module\":\"faq\",\"media_type\":\"application/pdf\"}"
```
