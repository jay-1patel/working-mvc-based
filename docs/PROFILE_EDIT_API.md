# Profile page Edit APIs (curl)

UI: **Tenants → Profile** (`ProfileEditor`)

**Edit profile** itself is local UI only (`setEditing(true)`).  
Saving / publishing hits these APIs.

Base: `http://10.100.100.43:9000`  
Auth headers: `username` + `session_id` (or Basic).  
Example tenant: `c`

Frontend wrappers: `frontend/src/lib/tenants.ts` → `tenantsApi.saveDraft` / `tenantsApi.publish`

---

## Flow (what the buttons call)

| UI button | API |
| --- | --- |
| Open page / reload | `GET /api/admin/tenants/{tenant_id}/detail` |
| **Edit profile** | _(no API — unlocks the form)_ |
| **Discard changes** | _(no API — reloads form from last detail)_ |
| **Save draft** (super admin only in UI) | `POST /api/admin/tenants/{tenant_id}/profile` |
| **Save & publish** / **Submit for approval** | 1) `POST .../profile` then 2) `POST .../publish` |
| **Done editing** | _(no API)_ |

For a tenant admin (`cars`), **Submit for approval** = save draft + publish.  
Publish either goes live (menu-only change) or queues a change request for super-admin approval.

---

## 1. Load profile (page open)

```bash
curl --request GET "http://10.100.100.43:9000/api/admin/tenants/c/detail" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID"
```

---

## 2. Save draft (Edit → change fields → save)

This is the API that **writes** profile changes. Body is `{ "snapshot": { ... } }`.  
Only send sections you changed; server deep-merges into the pending draft.

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/c/profile" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{
    "snapshot": {
      "brand": {
        "name": "MetroDrive Autos",
        "tagline": "Your neighbourhood car partner",
        "support_email": "support@example.com",
        "support_phone": "+919876543210",
        "website": "https://example.com",
        "timezone": "Asia/Kolkata",
        "address": "123 Main St"
      },
      "features": {
        "faq": true,
        "kb": true,
        "cart": false,
        "brochure_pdf": true
      },
      "guardrails": {
        "system_prompt": "Answer only from tenant knowledge.",
        "out_of_scope_reply": "I can only help with our products and services."
      },
      "notifications": {
        "handoff_emails": ["ops@example.com"],
        "complaint_emails": ["support@example.com"]
      }
    }
  }'
```

Success:

```json
{ "ok": true, "tenant_id": "c", "has_draft": true, "validation": [] }
```

Draft is **not** live yet. Bot still uses the last published version.

---

## 3. Publish / submit for approval (does “all the things”)

After a successful draft save, call publish:

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/c/publish" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{}'
```

### What publish does server-side

1. Loads the pending draft  
2. If caller is **tenant admin** and the change is **not menu-only** → queues  
   `publish_profile` in `POST /api/tenant-change-requests` logic (`queue_publish_for_approval`)  
3. Else validates profile + required contact fields, creates a new version, goes live, purges cache, syncs client pack  

Possible responses:

```json
{ "ok": true, "status": "pending_approval", "message": "Profile change sent for super admin approval — it goes live only once approved.", "request": { "...": "..." } }
```

```json
{ "ok": true, "version": 3, "active_intents": ["..."], "visible_buttons": ["..."] }
```

---

## Full “Edit → change → submit” in one PowerShell script

```powershell
$base = "http://10.100.100.43:9000"
$user = "cars"
$sid  = "YOUR_SESSION_ID"
$tid  = "c"
$h = @{ username = $user; session_id = $sid }

# 1) load
Invoke-RestMethod -Headers $h "$base/api/admin/tenants/$tid/detail"

# 2) save draft (example brand + features patch)
$draft = @{
  snapshot = @{
    brand = @{
      name = "MetroDrive Autos"
      support_email = "support@example.com"
      support_phone = "+919876543210"
      timezone = "Asia/Kolkata"
    }
    features = @{ faq = $true; kb = $true }
  }
} | ConvertTo-Json -Depth 8 -Compress

Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
  -Uri "$base/api/admin/tenants/$tid/profile" -Body $draft

# 3) publish / queue approval
Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
  -Uri "$base/api/admin/tenants/$tid/publish" -Body '{}'
```

---

## Super-admin approve (after pending_approval)

```bash
# list queue
curl --request GET "http://10.100.100.43:9000/api/admin/tenant-change-requests?status=pending" \
  --header "username: SUPER_ADMIN" \
  --header "session_id: SUPER_SESSION_ID"

# approve request id N
curl --request POST "http://10.100.100.43:9000/api/admin/tenant-change-requests/N/decision" \
  --header "username: SUPER_ADMIN" \
  --header "session_id: SUPER_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{"decision":"approved","note":"Looks good"}'
```

---

## Related (read what the bot sees)

```bash
curl --request POST "http://10.100.100.43:9000/api/admin/tenants/resolved" \
  --header "username: cars" \
  --header "session_id: YOUR_SESSION_ID" \
  --header "Content-Type: application/json" \
  --data '{}'
```
