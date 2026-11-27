/**
 * Chat attachments for the internal admin chat and the live inbox.
 *
 * Both upload a file to a tenant-scoped endpoint that hosts it on the
 * application's configured public domain and returns a descriptor.
 * Inbox replies send the descriptor as native WhatsApp image/document media.
 */

import { postForm } from './api'

const base = (tenantId: string) => `/api/admin/tenants/${encodeURIComponent(tenantId)}`

/** Keep in step with `MAX_ATTACHMENT_BYTES` in `backend/routes/admin.py`. */
export const MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
export const MAX_ATTACHMENT_LABEL = `${MAX_ATTACHMENT_BYTES / (1024 * 1024)} MB`

/** What the file picker offers and what the hint tells the admin. */
export const ATTACHMENT_ACCEPT = 'image/*,.pdf,.doc,.docx,.txt,.xlsx,.xls'
export const ATTACHMENT_TYPES_LABEL =
  'Images (JPG, PNG, GIF, WEBP, BMP) and documents (PDF, DOC, DOCX, TXT, XLS, XLSX)'

export interface Attachment {
  url: string
  name: string
  type: string
  size: number
  media_type?: string
}

export const attachmentsApi = {
  /** Upload raw file bytes via multipart — no base64 / JSON wrapping. */
  upload: async (tenantId: string, file: File, area: 'chat' | 'inbox'): Promise<Attachment> => {
    if (file.size > MAX_ATTACHMENT_BYTES) {
      throw new Error(`Attachments must be under ${MAX_ATTACHMENT_BYTES / (1024 * 1024)} MB`)
    }
    const form = new FormData()
    form.append('file', file, file.name)
    if (file.type) form.append('media_type', file.type)
    const path = area === 'chat' ? `${base(tenantId)}/chat/attach` : '/api/admin/tenants/inbox/attach'
    return postForm<Attachment>(path, form)
  },
}
