# Chats frontend API contract

The Send2-style Chats screen uses the existing tenant-scoped FastAPI routes.
The frontend sends the admin JWT as `Authorization: Bearer <token>` on every
request. A tenant administrator can access only their tenant; permissions are
also checked server-side.

## Hosting and forwarding

- Same origin: leave `VITE_API_ORIGIN` empty and forward `/api`, `/catalog`,
  `/ws`, `/crawl_images`, and `/uploaded_files` to the backend.
- Separate frontend: set `VITE_API_ORIGIN=https://your-api-host` at build time.
- Local Vite development already proxies API traffic to `BACKEND_ORIGIN`, which
  defaults to `http://localhost:9000`.
- A `401` clears the frontend session. Other failures surface the backend
  `detail` and `X-Request-Id`, allowing the error to be traced in Errors & health.

All paths below start with:

`/api/admin/tenants/{tenant_id}`

Path values are URL encoded by the frontend.

## APIs used by the Chats screen

| UI operation | Method and path | Request | Successful response |
| --- | --- | --- | --- |
| Load conversation queue | `GET /inbox?include_resolved=false` | none | `{ queue: InboxItem[], count, handoff_count }` |
| Load selected thread | `GET /conversations/{wa_id}?limit=300` | none | `{ wa_id, messages: ChatTurn[] }` |
| Load assignable agents | `GET /agents` | none | `{ agents: Agent[] }` |
| Assign chat | `POST /inbox/assign` | `{ wa_id, agent_id }` | `{ status, wa_id, agent_id }` |
| Take over / return to bot | `PUT /inbox/handover/{wa_id}` | `{ mode: "human" | "bot" }` | `{ status, wa_id, mode }` |
| Resolve | `POST /inbox/resolve/{wa_id}?reply=true` | none | `{ status, wa_id, notified, message }` |
| Send reply | `POST /inbox/{wa_id}/reply` | `{ message, attachment? }` | `{ status, wa_id, sent }` |
| Upload attachment | `POST /inbox/attach` | `{ filename, content, media_type? }` | `Attachment` |

The queue refreshes every 12 seconds. The shell separately polls the queue every
30 seconds to update the waiting-chat badge. Waiting-for-human conversations are
sorted first, followed by bot-handled conversations ordered by latest message.

## Response types

```ts
interface InboxItem {
  wa_id: string
  name: string
  last_message: string
  last_message_at: string
  turns: number
  bot_state: string | null
  handover_mode: 'bot' | 'human'
  assigned_agent_id: string | null
}

interface ChatTurn {
  id: number
  wa_id: string
  sender_name: string
  message: string
  response: string
  route: string
  created_at: string
  tenant_id?: string | null
  user_message?: string
}

interface Agent {
  agent_id: string
  username: string
  status: string
}

interface Attachment {
  url: string
  name: string
  type: string
  size: number
  media_type?: string
}
```

## Authentication APIs used before the screen opens

| Operation | Method and path |
| --- | --- |
| Check initial setup | `GET /api/auth/status` |
| Sign in | `POST /api/auth/login` |
| Restore current identity and permissions | `GET /api/auth/me` |
| Load available tenants | `GET /api/admin/tenants` |
| Load tenant profile/branding | `GET /api/admin/tenants/{tenant_id}/resolved` |

## Error behavior

- `400`: invalid mode, missing reply content, or invalid attachment.
- `401`: missing/expired bearer token.
- `403`: role, permission, or tenant-scope violation.
- `404`: conversation is outside the selected tenant or does not exist.
- `502`: WhatsApp provider rejected or failed to send the message.

Every failed response should retain its `X-Request-Id`. The shared frontend API
client already logs method, path, status, duration, backend detail, and request ID.
