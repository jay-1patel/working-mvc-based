# Admin panel API reference

Base URL: `http://192.168.0.122:9000`  
Authentication: every request uses the `username` and `session_id` headers and JSON fields.  
Scope: APIs currently referenced by the frontend admin panel. All entries below use `POST` as configured.

Total APIs: **134**

> Replace the sample username and session ID with the active credentials for the account making the request.

## Admin

### POST /api/admin/customers

Reads api admin customers data for the admin page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/customers' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/dashboard/overview

Creates or runs api admin dashboard overview data for the admin page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/dashboard/overview' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/upload/logo

Creates or runs api admin upload logo data for the admin page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/upload/logo' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Api Onboarding

### POST /api/admin/integration-requests

Reads api admin integration-requests data for the api onboarding page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/integration-requests' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/integration-requests/{request_id}/decision

Creates or runs api admin integration-requests value decision data for the api onboarding page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/integration-requests/{request_id}/decision' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/integration-requests/{request_id}/events

Reads api admin integration-requests value events data for the api onboarding page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/integration-requests/{request_id}/events' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/integration-requests

Reads api integration-requests data for the api onboarding page.

```bash
curl --location 'http://192.168.0.122:9000/api/integration-requests' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/integration-requests

Creates or runs api integration-requests data for the api onboarding page.

```bash
curl --location 'http://192.168.0.122:9000/api/integration-requests' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Audit

### POST /api/admin/audit-history/{event_id}

Reads api admin audit-history value data for the audit page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/audit-history/{event_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Auth

### POST /api/auth/admins/{username}

Deletes api auth admins value data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/admins/{username}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/admins/{username}

Updates api auth admins value data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/admins/{username}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/admins/{username}/regenerate-session

Creates or runs api auth admins value regenerate-session data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/admins/{username}/regenerate-session' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/create

Creates or runs api auth create data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/create' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/impersonate-tenant/{tenant_id}

Creates or runs api auth impersonate-tenant value data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/impersonate-tenant/{tenant_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/impersonate/{username}

Creates or runs api auth impersonate value data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/impersonate/{username}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/login

Creates or runs api auth login data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/login' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/me

Reads api auth me data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/me' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/onboarding-users

Creates or runs api auth onboarding-users data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/onboarding-users' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/auth/status

Reads api auth status data for the auth page.

```bash
curl --location 'http://192.168.0.122:9000/api/auth/status' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Callbacks

### POST /api/tenants/{tenant_id}/callbacks

Reads api tenants value callbacks data for the callbacks page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/callbacks' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenants/{tenant_id}/callbacks

Creates or runs api tenants value callbacks data for the callbacks page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/callbacks' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Conversations

### POST /api/admin/tenants/{tenant_id}/agents

Creates or runs api admin tenants value agents data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/agents' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/chat-history

Creates or runs api admin tenants value chat-history data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/chat-history' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/chat/thread

Creates or runs api admin tenants value chat thread data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/chat/thread' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/complaints

Creates or runs api admin tenants value complaints data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/complaints' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/complaints/delete

Creates or runs api admin tenants value complaints delete data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/complaints/delete' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/complaints/reply

Creates or runs api admin tenants value complaints reply data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/complaints/reply' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/complaints/update

Creates or runs api admin tenants value complaints update data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/complaints/update' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/conversations

Reads api admin tenants value conversations data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/conversations' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/conversations

Creates or runs api admin tenants value conversations data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/conversations' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/conversations/{wa_id}

Creates or runs api admin tenants value conversations value data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/conversations/{wa_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/conversations/detail

Creates or runs api admin tenants value conversations detail data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/conversations/detail' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/customer-360/{wa_id}

Reads api admin tenants value customer-360 value data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/customer-360/{wa_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox

Creates or runs api admin tenants value inbox data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/assign

Creates or runs api admin tenants value inbox assign data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/assign' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/attach

Creates or runs api admin tenants value inbox attach data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/attach' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/events

Reads api admin tenants value inbox events data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/events' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/handover

Creates or runs api admin tenants value inbox handover data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/handover' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/menu

Creates or runs api admin tenants value inbox menu data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/menu' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/reply

Creates or runs api admin tenants value inbox reply data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/reply' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/inbox/resolve

Creates or runs api admin tenants value inbox resolve data for the conversations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/inbox/resolve' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Crawl

### POST /api/admin/tenants/{tenant_id}/crawl-runs/{run_id}

Reads api admin tenants value crawl-runs value data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/crawl-runs/{run_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/crawl

Creates or runs api admin tenants crawl data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/crawl' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/crawl-runs

Creates or runs api admin tenants crawl-runs data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/crawl-runs' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/crawl-runs/approve

Creates or runs api admin tenants crawl-runs approve data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/crawl-runs/approve' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/crawl-runs/export

Creates or runs api admin tenants crawl-runs export data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/crawl-runs/export' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/crawl-runs/reject

Creates or runs api admin tenants crawl-runs reject data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/crawl-runs/reject' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/crawl-runs/staged

Creates or runs api admin tenants crawl-runs staged data for the crawl page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/crawl-runs/staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Integrations

### POST /api/tenants/{tenant_id}/integrations

Reads api tenants value integrations data for the integrations page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/integrations' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenants/{tenant_id}/integrations/{provider}/config

Creates or runs api tenants value integrations value config data for the integrations page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/integrations/{provider}/config' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenants/{tenant_id}/integrations/{provider}/test

Creates or runs api tenants value integrations value test data for the integrations page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/integrations/{provider}/test' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenants/{tenant_id}/payments/create-session

Creates or runs api tenants value payments create-session data for the integrations page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/payments/create-session' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenants/{tenant_id}/shipping/book-shipment

Creates or runs api tenants value shipping book-shipment data for the integrations page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/shipping/book-shipment' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenants/{tenant_id}/shipping/track/{awb}

Reads api tenants value shipping track value data for the integrations page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenants/{tenant_id}/shipping/track/{awb}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Offerings

### POST /api/admin/tenants/{tenant_id}/ingest-file

Creates or runs api admin tenants value ingest-file data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/ingest-file' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings

Reads api admin tenants value offerings data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings

Creates or runs api admin tenants value offerings data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/{offering_id}

Deletes api admin tenants value offerings value data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/{offering_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/{offering_id}

Updates api admin tenants value offerings value data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/{offering_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/approve-staged

Creates or runs api admin tenants value offerings approve-staged data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/approve-staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/categories

Reads api admin tenants value offerings categories data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/categories' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/ingest-pdf

Creates or runs api admin tenants value offerings ingest-pdf data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/ingest-pdf' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/staged

Deletes api admin tenants value offerings staged data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/staged

Reads api admin tenants value offerings staged data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/offerings/upload-pdf

Creates or runs api admin tenants value offerings upload-pdf data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/offerings/upload-pdf' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/products/approve-staged

Creates or runs api admin tenants value products approve-staged data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/products/approve-staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/products/staged

Deletes api admin tenants value products staged data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/products/staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/products/staged

Reads api admin tenants value products staged data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/products/staged' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/products/upload-pdf

Creates or runs api admin tenants value products upload-pdf data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/products/upload-pdf' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/record-schema

Reads api admin tenants value record-schema data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/record-schema' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/record-schema/columns

Creates or runs api admin tenants value record-schema columns data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/record-schema/columns' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/record-schema/columns/{key}

Deletes api admin tenants value record-schema columns value data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/record-schema/columns/{key}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/record-schema/columns/{key}

Updates api admin tenants value record-schema columns value data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/record-schema/columns/{key}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/record-schema/reset

Creates or runs api admin tenants value record-schema reset data for the offerings page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/record-schema/reset' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Onboarding Kits

### POST /api/admin/onboarding-kits/{vertical}/{fmt}

Reads api admin onboarding-kits value value data for the onboarding kits page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/onboarding-kits/{vertical}/{fmt}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/onboarding-kits/list

Creates or runs api admin onboarding-kits list data for the onboarding kits page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/onboarding-kits/list' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/onboarding/stage

Creates or runs api admin onboarding stage data for the onboarding kits page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/onboarding/stage' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/onboarding/publish

Creates or runs api admin tenants value onboarding publish data for the onboarding kits page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/onboarding/publish' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/onboarding/stage

Creates or runs api admin tenants value onboarding stage data for the onboarding kits page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/onboarding/stage' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Tenant Approvals

### POST /api/admin/tenant-change-requests

Reads api admin tenant-change-requests data for the tenant approvals page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenant-change-requests' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenant-change-requests/{request_id}/decision

Creates or runs api admin tenant-change-requests value decision data for the tenant approvals page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenant-change-requests/{request_id}/decision' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenant-change-requests/{request_id}/events

Reads api admin tenant-change-requests value events data for the tenant approvals page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenant-change-requests/{request_id}/events' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenant-change-requests

Reads api tenant-change-requests data for the tenant approvals page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenant-change-requests' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenant-change-requests

Creates or runs api tenant-change-requests data for the tenant approvals page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenant-change-requests' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/tenant-change-requests/mine

Creates or runs api tenant-change-requests mine data for the tenant approvals page.

```bash
curl --location 'http://192.168.0.122:9000/api/tenant-change-requests/mine' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Tenant Chat

### POST /api/admin/tenants/{tenant_id}/chat/attach

Creates or runs api admin tenants value chat attach data for the tenant chat page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/chat/attach' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/chat/message/{msg_id}

Deletes api admin tenants value chat message value data for the tenant chat page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/chat/message/{msg_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/chat/send

Creates or runs api admin tenants value chat send data for the tenant chat page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/chat/send' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/chat/users

Reads api admin tenants value chat users data for the tenant chat page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/chat/users' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Tenant Files

### POST /api/admin/tenants/{tenant_id}/files

Creates or runs api admin tenants value files data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/auto-bifurcate

Creates or runs api admin tenants value files auto-bifurcate data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/auto-bifurcate' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/bifurcate-existing

Creates or runs api admin tenants value files bifurcate-existing data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/bifurcate-existing' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/delete

Creates or runs api admin tenants value files delete data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/delete' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/download

Creates or runs api admin tenants value files download data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/download' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/image

Creates or runs api admin tenants value files image data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/image' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/preview

Creates or runs api admin tenants value files preview data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/preview' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/files/upload

Creates or runs api admin tenants value files upload data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/files/upload' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/knowledge-gaps

Creates or runs api admin tenants value knowledge-gaps data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/knowledge-gaps' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/knowledge-gaps/create-faq

Creates or runs api admin tenants value knowledge-gaps create-faq data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/knowledge-gaps/create-faq' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/knowledge-gaps/resolve

Creates or runs api admin tenants value knowledge-gaps resolve data for the tenant files page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/knowledge-gaps/resolve' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Tenant Operations

### POST /api/admin/tenants/{tenant_id}/customers

Creates or runs api admin tenants value customers data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/customers' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/customers/export

Creates or runs api admin tenants value customers export data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/customers/export' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/orders

Reads api admin tenants value orders data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/orders' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/orders/{order_id}

Deletes api admin tenants value orders value data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/orders/{order_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/orders/{order_id}

Reads api admin tenants value orders value data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/orders/{order_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/orders/{order_id}

Updates api admin tenants value orders value data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/orders/{order_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/orders/stats

Reads api admin tenants value orders stats data for the tenant operations page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/orders/stats' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

## Tenants

### POST /api/admin/tenants/{tenant_id}

Deletes api admin tenants value data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/crawl-schedule

Deletes api admin tenants value crawl-schedule data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/crawl-schedule' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/crawl-schedule

Reads api admin tenants value crawl-schedule data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/crawl-schedule' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/crawl-schedule

Updates api admin tenants value crawl-schedule data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/crawl-schedule' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/crawl-schedule/run

Creates or runs api admin tenants value crawl-schedule run data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/crawl-schedule/run' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/detail

Creates or runs api admin tenants value detail data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/detail' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/intents/{intent_name}

Updates api admin tenants value intents value data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/intents/{intent_name}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/mobile-number

Creates or runs api admin tenants value mobile-number data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/mobile-number' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/phone-id

Creates or runs api admin tenants value phone-id data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/phone-id' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/profile

Creates or runs api admin tenants value profile data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/profile' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/publish

Creates or runs api admin tenants value publish data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/publish' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/rollback

Creates or runs api admin tenants value rollback data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/rollback' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/scrape-website

Creates or runs api admin tenants value scrape-website data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/scrape-website' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/smoke

Reads api admin tenants value smoke data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/smoke' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/test-question

Creates or runs api admin tenants value test-question data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/test-question' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/tokens

Reads api admin tenants value tokens data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/tokens' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/tokens

Creates or runs api admin tenants value tokens data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/tokens' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/tokens/{token_id}

Deletes api admin tenants value tokens value data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/tokens/{token_id}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/versions

Reads api admin tenants value versions data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/versions' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/versions/{version}

Reads api admin tenants value versions value data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/versions/{version}' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/{tenant_id}/webhook-secret

Updates api admin tenants value webhook-secret data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/{tenant_id}/webhook-secret' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/active-test-tenant

Reads api admin tenants active-test-tenant data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/active-test-tenant' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/active-test-tenant

Creates or runs api admin tenants active-test-tenant data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/active-test-tenant' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/auto-onboard-execute

Creates or runs api admin tenants auto-onboard-execute data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/auto-onboard-execute' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/auto-onboard-preview

Creates or runs api admin tenants auto-onboard-preview data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/auto-onboard-preview' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/list

Creates or runs api admin tenants list data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/list' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

### POST /api/admin/tenants/resolved

Creates or runs api admin tenants resolved data for the tenants page.

```bash
curl --location 'http://192.168.0.122:9000/api/admin/tenants/resolved' --header 'username: test_support_' --header 'session_id: 3047_1795425829_1673129d65' --header 'Content-Type: application/json' --data '{"username":"test_support_","session_id":"3047_1795425829_1673129d65"}'
```

