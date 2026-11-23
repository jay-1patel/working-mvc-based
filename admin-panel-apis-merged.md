# Admin panel API reference

## Sidebar page APIs

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

---

## Super-admin APIs

Base URL: `http://192.168.0.122:9000`

These are the APIs used by the super-admin landing flow and tenant support login added today. The backend methods are kept as implemented.

## 1. Check authentication setup

```bash
curl --location 'http://192.168.0.122:9000/api/auth/status'
```

Checks whether any admin account exists before showing the login screen.

## 2. Super-admin login

```bash
curl --location 'http://192.168.0.122:9000/api/auth/login' --header 'Content-Type: application/json' --data '{"username":"customer_care","session_id":"YOUR_SESSION_ID"}'
```

Authenticates the super-admin and returns the live session credentials.

## 3. Read current admin identity

```bash
curl --location 'http://192.168.0.122:9000/api/auth/me' --header 'username: customer_care' --header 'session_id: YOUR_SESSION_ID'
```

Returns the current user, role, permissions, and customer-care status.

## 4. Load onboarded users

```bash
curl --location 'http://192.168.0.122:9000/api/auth/onboarding-users' --header 'username: customer_care' --header 'session_id: YOUR_SESSION_ID' --header 'Content-Type: application/json' --data '{"username":"customer_care","session_id":"YOUR_SESSION_ID"}'
```

Loads tenant admins and sub-admins for the Onboarded users page.

The response provides the table data used by the page:

- `username`
- `email`
- `role`
- `tenant_id`
- `created_at`
- `onboarding_approved`

## 5. Open a tenant by username

```bash
curl --location 'http://192.168.0.122:9000/api/auth/impersonate/test_support_' --header 'username: customer_care' --header 'session_id: YOUR_SESSION_ID' --header 'Content-Type: application/json' --data '{"username":"customer_care","session_id":"YOUR_SESSION_ID"}'
```

Creates or reuses a live support session for the selected tenant user.

The **Login** button on every Onboarded users row calls this endpoint. The returned `username`, `session_id`, and tenant information are then used to open the selected tenant console.

## 6. Open a tenant by tenant ID

```bash
curl --location 'http://192.168.0.122:9000/api/auth/impersonate-tenant/c88' --header 'username: customer_care' --header 'session_id: YOUR_SESSION_ID' --header 'Content-Type: application/json' --data '{"username":"customer_care","session_id":"YOUR_SESSION_ID"}'
```

Opens the first eligible admin account belonging to the selected tenant.

## 7. Load tenant list for the super-admin switcher

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants' --header 'username: customer_care' --header 'session_id: YOUR_SESSION_ID'
```

Returns tenants visible to the super-admin console.

## 8. Load selected tenant details

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/c88/detail' --header 'username: test_support_' --header 'session_id: TARGET_SESSION_ID' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"TARGET_SESSION_ID"}'
```

Returns the selected tenant’s effective profile, configuration layers, menu, features, and related details after support login.

## Authentication notes

- Use the super-admin `username` and `session_id` for APIs 3–7.
- After opening a tenant, use the returned target `username` and `session_id` for tenant details and tenant console APIs.
- `/api/auth/login` is the only login request and does not require authentication headers.
- Do not change `GET` endpoints to `POST`; the backend method must match the route.
