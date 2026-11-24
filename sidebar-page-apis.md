# Sidebar page APIs (curl)

Base URL: `http://127.0.0.1:9000`  
Auth: `username` + `session_id` headers only (not repeated in body).  
Sample tenant path id: `c` — change credentials / tenant / `wa_id` / `run_id` as needed.

```text
username: test_support_
session_id: 3047_1795425829_1673129d65
```

---

## **Auth / Privileges**

Unified RBAC for sidebar pages (Chats, Dashboard, Profile, Upload/Website crawler, Menu).  
Returns `pages`, `permissions`, `features`, `role`, `tenant_id`, `is_tenant_view_only`.

```bash
curl --location 'http://127.0.0.1:9000/api/auth/privileges' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## **Dashboard**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/dashboard/overview?days=7&limit=8' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/detail' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"include_resolved":false}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/chat-history' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"days":1,"limit":500}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/customers' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"q":"","limit":500}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/staged' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/errors?limit=100&tenant_id=c' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## **Chats**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"include_resolved":true}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/conversations' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"limit":500}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/chat/thread' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","limit":300}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/agents' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/events' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--header 'Accept: text/event-stream' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/reply' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","message":"Hello from admin"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/menu' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/handover' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","mode":"human"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/assign' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","agent_id":"agent1"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/resolve' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"wa_id":"919999999999","reply":true}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/inbox/attach' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--form 'file=@"/path/to/file.pdf"'
```

---

## **Profile**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/detail' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/profile' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"snapshot":{}}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/publish' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## **WhatsApp → WhatsApp menu**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/detail' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/resolved' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## **WhatsApp → Profile menu**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/detail' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/profile' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"snapshot":{}}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/c/publish' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

---

## **Website crawler**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"url":"https://example.com"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/staged' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/approve' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/reject' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/crawl-runs/export' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"run_id":1,"format":"json"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/files' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/files/upload' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--form 'module="kb"' \
--form 'file=@"/path/to/file.pdf"'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/files/delete' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"example.pdf"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/files/preview' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"example.pdf"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/files/download' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filename":"example.pdf"}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/files/bifurcate-existing' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"filenames":["example.pdf"]}'
```

---

## **Customers**

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/customers' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"q":"","limit":200}'
```

```bash
curl --location 'http://127.0.0.1:9000/api/admin/tenants/customers/export' \
--header 'username: test_support_' \
--header 'session_id: 3047_1795425829_1673129d65' \
--header 'Content-Type: application/json' \
--data '{"format":"csv"}'
```
