# Admin panel API reference (frontend only)

Only endpoints the React console actually calls.  
Every curl is **POST**. Auth is header-only (`username` + `session_id`), not repeated in the body.

```text
Base:       http://127.0.0.1:9000
username:   test_support_
session_id: 3047_1795425829_1673129d65
Sample tenant id: c
Sample wa_id:     919999999999
```

Tags: `#auth` `#super-admin` `#tenant` `#page:<route>`

---

## Login / bootstrap

`#page:login` `#auth`

### Check whether any admin exists
Sees if the first-admin setup screen should show.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/status' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Sign in
Authenticates with username + session_id and returns live credentials.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/login' \
--header 'Content-Type: application/json' \
--data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### Create first super admin
Used only when no admins exist yet.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/first-admin' \
--header 'Content-Type: application/json' \
--data '{"username":"super","password":"ChangeMe1!","email":null}'
```

### Load current identity
Returns role, permissions, tenant_id, customer-care flags (app boot + after login).

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/me' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Report a client-side failure
Browser posts unreachable/parse errors for the Errors screen.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/client-errors' \
--header 'Content-Type: application/json' \
--data '{"message":"Cannot reach backend","detail":"","api":"POST /api/admin/tenants/list"}'
```

---

## Dashboard / Super Today

`#page:dashboard` `#super-admin`

### Platform overview charts
Loads 7-day overview stats for the graphical home.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/dashboard/overview' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"days":7,"limit":8}'
```

---

## Businesses / tenant list

`#page:tenants` `#super-admin` `#tenant`

### List tenants
Fills the Businesses switcher / tenant registry.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/list' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Create tenant
Registers a new company from the console.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"id":"acme","display_name":"Acme","vertical":"tours_travel"}'
```

### Delete tenant
Removes a company from the registry.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/acme' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Set WhatsApp phone id
Binds the WABA phone number id on a tenant.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/phone-id' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"phone_number_id":"123456"}'
```

### Get / set active test tenant
Used by WhatsApp Tester to pick which tenant receives simulated traffic.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/active-test-tenant' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/active-test-tenant' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"tenant_id":"c"}'
```

---

## Tenant console bootstrap (shared)

`#tenant` — used by Profile, Menu, Layers, Today, and most tenant screens.

### Resolved live profile
Effective menu, features, brand, vocabulary after layers merge.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/resolved' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Layer detail
Draft / override layers for the selected tenant.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/detail' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Dashboard — Today

`#page:overview` `#tenant`

### Recent errors for this tenant
“Needs attention” strip on the tenant Today screen.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/errors' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":100,"tenant_id":"c"}'
```

---

## Chats (live inbox)

`#page:inbox` `#tenant`

### List inbox queue
Open / resolved conversations waiting for agents.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"include_resolved":true}'
```

### List conversation threads
Searchable thread list for the chats sidebar.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/conversations' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"search":"","limit":100}'
```

### Open a chat thread
Loads messages for one WhatsApp customer.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/chat/thread' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","limit":300}'
```

### List agents
Agents available for assign.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/agents' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Reply to customer

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/reply' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","message":"Hello from admin"}'
```

### Send WhatsApp menu

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/menu' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999"}'
```

### Switch handover bot ↔ human

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/handover' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","mode":"human"}'
```

### Assign agent

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/assign' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","agent_id":"agent1"}'
```

### Resolve conversation

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/resolve' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","reply":true}'
```

### Attach file in inbox

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/attach' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"a.png","content":"BASE64...","media_type":"image/png"}'
```

### Inbox live events (SSE)
Realtime updates for the Chats panel.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/inbox/events' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Accept: text/event-stream' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Past chats

`#page:chat-history` `#tenant`

### Load chat history
Historical turns filtered by days / search / wa_id.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/chat-history' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"days":7,"search":"","limit":200}'
```

---

## Complaints / Help requests

`#page:complaints` `#tenant`

### List complaints

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/complaints' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"status":"open","limit":100}'
```

### Update complaint status / priority / assignee

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/complaints/update' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"ticket_id":"T1","status":"in_progress"}'
```

### Reply on a complaint ticket

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/complaints/reply' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"ticket_id":"T1","message":"We are looking into it"}'
```

### Delete complaint

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/complaints/delete' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"ticket_id":"T1"}'
```

---

## Callbacks

`#page:callbacks` `#tenant`

### List callbacks

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/callbacks' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":50}'
```

### Create callback manually

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/callbacks' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"customer_name":"Riya","wa_id":"919999999999","callback_type":"sales","purpose":"Package enquiry"}'
```

### Schedule callback (Meet link)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/callbacks/CB1/schedule' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"agent_id":"a1","agent_name":"Sam","start_time":"2026-11-25T10:00:00","end_time":"2026-11-25T10:30:00"}'
```

### Complete callback

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/callbacks/CB1/complete' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"meeting_notes":"Done","outcome":"success"}'
```

### Cancel callback

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/callbacks/CB1/cancel' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"reason":"customer cancelled"}'
```

---

## Profile / WhatsApp menu / Profile menu

`#page:profile` `#page:menu` `#page:profile-menu` `#page:menu-edit` `#tenant`

### Save profile draft
Persists brand, hours, menu, features, guardrails (also menu editor).

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/profile' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"snapshot":{}}'
```

### Publish profile
Promotes draft to live version.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/publish' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Offerings / Records & prices

`#page:offerings` `#page:records` `#tenant`

### List offerings

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/offerings' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"include_inactive":false}'
```

### Create offering

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/offerings' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"Kerala 5N","category":"Family","price":24999}'
```

### Update offering

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/offerings/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"Kerala 5N Deluxe"}'
```

### Delete offering

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/offerings/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"hard":false}'
```

### Get record schema (custom columns)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/record-schema' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Add column

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/record-schema/columns' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"key":"duration","label":"Duration","type":"text"}'
```

### Update column

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/record-schema/columns/duration' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"label":"Trip duration"}'
```

### Delete column

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/record-schema/columns/duration' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Reset columns to vertical defaults

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/record-schema/reset' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Customers

`#page:customers` `#tenant`

### List this tenant’s customers

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/customers' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"q":"","limit":200}'
```

### Platform-wide customers (legacy super-admin list)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/customers' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"q":"","limit":200}'
```

### Export customers CSV

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/customers/export' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"format":"csv"}'
```

---

## Orders

`#page:orders` `#tenant`

### List tenant orders

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/orders' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":100}'
```

### Platform-wide orders (legacy)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/orders' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":100}'
```

---

## Distributors / Partners

`#page:distributors` `#tenant`

### List distributors

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/distributors' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Create distributor

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/distributors' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","name":"Reseller A","tier":"Gold"}'
```

### Update distributor

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/distributors/919999999999' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"Reseller A","tier":"Platinum"}'
```

### Delete distributor

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/distributors/919999999999' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Campaigns

`#page:campaigns` `#tenant`

### List campaigns + stats

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Create campaign

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"Diwali","message_template":"Hi {{name}}","schedule_mode":"now"}'
```

### Update campaign

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"Diwali","message_template":"Hi {{name}}","schedule_mode":"now"}'
```

### Delete campaign

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### List recipients

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/recipients' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Send to full audience

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/1/send' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Send to selected wa_ids

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/1/send-selection' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_ids":["919999999999"]}'
```

### Test-send to one number

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/1/test-send' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999"}'
```

### Templates — list / create / set status / delete

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/templates' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/templates' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"Welcome","category":"MARKETING","body":"Hello"}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/templates/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"status":"APPROVED"}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/templates/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Segments — list / create / update / delete

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/segments' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/segments' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"VIPs","audience_type":"customers","criteria":{}}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/segments/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"name":"VIPs","audience_type":"customers","criteria":{}}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/segments/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Upload campaign media

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/campaigns/media' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--form 'file=@"/path/to/banner.jpg"'
```

---

## Website crawler / Website knowledge

`#page:website-crawler` `#page:website-knowledge` `#tenant`

### List crawl runs + schedule

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Start a crawl

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/crawl' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"url":"https://example.com"}'
```

### Load staged crawl result

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/staged' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

### Approve staged knowledge

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/approve' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

### Reject staged knowledge

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/reject' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

### Export staged crawl

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/export' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1,"format":"json"}'
```

---

## Uploads (FAQ / KB files)

`#page:uploads` `#tenant`

### List files

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/files' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"module":"faq"}'
```

### Upload file (base64 JSON)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/files/upload' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"faq.pdf","content":"BASE64...","module":"faq"}'
```

### Delete file

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/files/delete' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"faq.pdf"}'
```

### Preview / download file

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/files/preview' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"faq.pdf"}'
```

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/files/download' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"faq.pdf"}'
```

### Auto-bifurcate uploaded PDFs

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/files/auto-bifurcate' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"files":[{"filename":"kit.pdf","content":"BASE64..."}],"auto_publish":false}'
```

### Bifurcate existing files

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/files/bifurcate-existing' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filenames":["kit.pdf"],"auto_publish":false}'
```

---

## Settings / Knowledge gaps

`#page:settings` `#tenant`

### List unanswered queries

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/knowledge-gaps' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Mark gap resolved

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/knowledge-gaps/resolve' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"gap_id":1,"resolved":true}'
```

### Create FAQ from a gap

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/knowledge-gaps/create-faq' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"question":"Do you fly to Bali?","answer":"Yes — ask for dates."}'
```

---

## Intents / IT info pages

`#page:intents` `#page:projects` `#tenant`

### Save one intent (also Projects / Technologies / Careers / Benefits text)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/intents/greeting' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"answer":"Hi!","keywords":["hello"],"enabled":true}'
```

---

## Versions

`#page:versions` `#tenant`

### List versions

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/versions' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Get one version snapshot

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/versions/3' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Rollback to a version

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/rollback' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"version":3}'
```

---

## Layers

`#page:layers` `#tenant`

Uses **Layer detail** (`POST /api/admin/tenants/c/detail`) from Tenant console bootstrap.

---

## Connections / Tokens

`#page:tokens` `#tenant`

### List tokens

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/tokens' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Create token

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/tokens' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"label":"Partner API"}'
```

### Revoke token

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/tokens/1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Admin chat

`#page:chat` `#tenant`

### List chat users

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/chat/users' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Send admin chat message

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/chat/send' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","message":"ping"}'
```

### Attach in admin chat

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/chat/attach' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"a.png","content":"BASE64...","media_type":"image/png"}'
```

---

## Test & smoke

`#page:test` `#tenant`

### Ask a test question through the bot

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/test-question' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"message":"What packages do you have?"}'
```

### Run smoke checks

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/smoke' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## WhatsApp Tester

`#page:whatsapp-tester` `#tenant`

### Simulate inbound WhatsApp message

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/test-simulator' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"test-user","message":"hi","tenant_id":"c"}'
```

### Reset simulator session

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/test-simulator/reset' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"test-user","tenant_id":"c"}'
```

---

## API access (tenant)

`#page:api-access` `#tenant`

### List my integration requests

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/integration-requests' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Submit integration request

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/integration-requests' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"provider":"stripe","purpose":"Checkout payments"}'
```

### List configured integrations

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/integrations' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Save provider config

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/integrations/stripe/config' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"config":{"secret_key":"sk_test_…"}}'
```

### Test provider connection

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/integrations/stripe/test' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Create payment session

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/payments/create-session' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"amount":1000,"currency":"INR"}'
```

### Book shipment

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/shipping/book-shipment' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"order_id":"ORD1"}'
```

### Track shipment

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenants/c/shipping/track/AWB123' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Team

`#page:team` `#super-admin`

### List admins

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/admins' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Create admin / sub-admin

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/create' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"username":"ops1","password":"ChangeMe1!","role":"admin","tenant_id":"c"}'
```

### Update admin permissions / email / tenant

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/admins/ops1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"permissions":{},"email":null,"tenant_id":"c"}'
```

### Reset password

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/admins/ops1/reset-password' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"new_password":"ChangeMe1!"}'
```

### Delete admin

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/admins/ops1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Onboarding users (Customer care)

`#page:onboarding-users` `#super-admin`

### List onboarded users

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/onboarding-users' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Impersonate by username (Login into tenant)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/impersonate/ops1' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Impersonate by tenant id

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/impersonate-tenant/c' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Register / first-login wizard

`#page:register` `#auth` `#tenant`

### Complete first-login setup
Creates tenant, binds WhatsApp, publishes v1, scopes the admin.

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/auth/first-login/complete' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"tenant_id":"wanderly","vertical":"tours_travel","display_name":"Wanderly","waba_phone_id":"123","snapshot":{}}'
```

### List onboarding kits

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/onboarding-kits/list' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Download kit file

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/onboarding-kits/tours_travel/pdf' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Stage kit/PDF (no tenant yet)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/onboarding/stage' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"kit.pdf","content":"BASE64..."}'
```

### Stage against existing tenant

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/onboarding/stage' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"kit.pdf","content":"BASE64..."}'
```

### Publish staged onboarding

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenants/c/onboarding/publish' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Upload logo

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/upload/logo' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--form 'file=@"/path/to/logo.png"'
```

---

## Tenant change requests

`#page:tenant-requests` `#super-admin` `#tenant`

### My requests

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenant-change-requests/mine' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Submit request

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/tenant-change-requests' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"kind":"profile","payload":{}}'
```

### List all (super admin)

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenant-change-requests' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Approve / reject

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenant-change-requests/1/decision' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"decision":"approved","note":"ok"}'
```

### Request event log

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/tenant-change-requests/1/events' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## API requests review (super admin)

`#page:api-requests` `#super-admin`

### List all integration requests

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/integration-requests' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Decide on a request

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/integration-requests/1/decision' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"decision":"approved","note":"ok"}'
```

### Request event log

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/integration-requests/1/events' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## Audit history

`#page:audit-history` `#super-admin`

### List audit events

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/audit-history' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":50}'
```

### Audit statistics

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/audit-statistics' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### One audit event

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/audit-history/123' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

### Export audit log

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/audit-export' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":1000}'
```

---

## Errors panel

`#page:errors` `#super-admin`

### List API / runtime errors

```bash
curl --location --request POST 'http://127.0.0.1:9000/api/admin/errors' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":100}'
```

---

## Notes

- Source: `frontend/src/lib/*` + a few components (`overview-dashboard`, `today-panel`, `errors-panel`, `admin-chat`, `chats-panel`, `onboarding-kit-widget`).
- Not included: `/api/auth/privileges` and any other backend route the UI never calls.
- Some backends still register GET/PUT/DELETE; these curls use **POST** as requested for client testing. If a route rejects POST, the live FastAPI method may still be GET/PUT/DELETE — check the route if a call fails.
