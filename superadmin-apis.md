# Super-admin APIs

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
