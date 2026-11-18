# Server deployment requirements (excluding `requirements.txt`)

Everything you need to install / provision **besides** `pip install -r requirements.txt`.

---

## 1. Machine baseline

| Item | Recommendation |
|---|---|
| OS | Linux (Ubuntu 22.04+) preferred; Windows Server also works |
| CPU | 4+ cores (8+ if running Ollama locally with 7B–8B models) |
| RAM | **16 GB min**; **32 GB** recommended with local Ollama + embeddings |
| Disk | **40 GB+** free (models, Playwright browsers, uploads, SQLite, FAISS) |
| Network | Outbound HTTPS to Send2, Hugging Face (first model download), optional Groq/Mistral |

**Rule:** run **one** `backend/main.py` process against **one** `faq.db`. Two processes = double WhatsApp replies.

---

## 2. Runtime installs (system)

### Python
- **Python 3.11 or 3.12** (project Dockerfile uses 3.11; avoid 3.15 — `faiss-cpu` breaks)
- `venv` / `pip` / `wheel`
- Linux build helpers if wheels fail: `gcc`, `g++`, `python3-dev`

### Windows only
- **Microsoft Visual C++ Redistributable (x64)** — required for PyTorch DLLs

### Linux packages (apt example)
```bash
sudo apt-get update && sudo apt-get install -y \
  tesseract-ocr \
  libgl1 \
  libglib2.0-0 \
  gcc g++ \
  curl ca-certificates
```

### OCR (scanned / image PDFs)
| OS | Install |
|---|---|
| Ubuntu/Debian | `sudo apt-get install -y tesseract-ocr` |
| Windows | Tesseract OCR (UB-Mannheim) → usually `C:\Program Files\Tesseract-OCR\tesseract.exe` |

Set in `routing/.env`:
```env
TESSERACT_CMD=/usr/bin/tesseract
# or Windows:
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Playwright Chromium (website crawl / JS pages)
After Python deps:
```bash
python -m playwright install chromium
# Linux may also need:
# python -m playwright install-deps chromium
```

### Node.js (Tenant Console frontend)
- **Node.js 20+** and **npm**
```bash
cd frontend
npm install
npm run build          # production static assets
# or: npm run dev      # local only, port 5173 (proxies to :9000)
```

Serve the built frontend behind nginx, or let the backend static mount serve it if configured that way.

---

## 3. External / local services

### A. LLM (pick one — required)

| Provider | What to install / configure |
|---|---|
| **Ollama (local)** | Install [Ollama](https://ollama.com), then `ollama pull qwen3:8b` (or your `OLLAMA_MODEL`). Must listen on `http://localhost:11434` |
| **Groq** | No install — set `API_PROVIDER=groq` + `GROQ_API_KEY` |
| **Mistral** | No install — set `API_PROVIDER=mistral` + `MISTRAL_API_KEY` |

Used for: chat answers, classification, PDF auto-bifurcation.

### B. WhatsApp CPaaS — Send2.digital (required for live WhatsApp)
Account + credentials (no local install):
- Username / password
- Business number (`SEND2_NUMBER`)
- API endpoints (session send, incoming-report poll, list menu, quick buttons, media, incoming-entry)

### C. Optional SaaS
| Service | Purpose |
|---|---|
| **ImgHippo** (or similar) | Public image hosting for WhatsApp media (`IMGHIPPO_API_KEY`) |
| **SMTP** | Admin OTP / password-reset emails |
| **Cloudflare Tunnel / ngrok** | Public HTTPS URL for media + webhooks (`PUBLIC_BASE_URL`) |
| **Hookdeck** | Optional webhook mirror (`HKDEK_WEBHOOK_URL`) |
| **Hugging Face** | First-time download of embedding/reranker models (or pre-cache offline) |

### D. Database
- **SQLite file** only (`faq.db`) — no Postgres/MySQL required
- Persist path via `ROUTING_DB_PATH`
- Back up this file regularly

---

## 4. Python app setup (after system installs)

```bash
cd mvc-based-code-main
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

Create first admin (once):
- Open console → first-admin setup, or `POST /api/auth/first-admin`

Run:
```bash
python backend/main.py
# listens on 0.0.0.0:9000
```

---

## 5. Ports & firewall

| Port | Service |
|---|---|
| **9000** | Unified FastAPI bot (must be open to admin users / reverse proxy) |
| **11434** | Ollama (localhost only is fine if LLM is on same box) |
| **5173** | Frontend Vite dev only (not for production) |
| **443 / 80** | nginx / reverse proxy (recommended in front of 9000) |

Outbound HTTPS must be allowed to:
- `api.send2.digital`
- `huggingface.co` (first model pull)
- Groq / Mistral if used
- ImgHippo / SMTP host if used

---

## 6. Environment checklist (`routing/.env`)

### Must set for WhatsApp demo/prod
```env
SEND2_USERNAME=...
SEND2_PASSWORD=...
SEND2_NUMBER=...
SEND2_POLLER_ENABLED=1
SEND2_SESSION_MSG_URL=https://api.send2.digital/devdesk/session-msg-send
SEND2_INCOMING_URL=https://api.send2.digital/devdesk/incoming-report
SEND2_INCOMING_ENTRY_URL=https://api.send2.digital/devdesk/AI_chatbot_API_incomingentry
SEND2_LIST_MENU_URL=https://api.send2.digital/whatsapp/attachment/list_messages
SEND2_QUICK_BUTTON_URL=https://api.send2.digital/whatsapp/attachment/session_msg_quickbtn
SEND2_MEDIA_URL=https://api.send2.digital/devdesk/media
ROUTING_DB_PATH=/absolute/path/to/faq.db
```

### Must set for LLM
```env
API_PROVIDER=ollama          # or groq / mistral
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=qwen3:8b
```

### Must set for admin security (change defaults!)
```env
ADMIN_SECRET_KEY=long-random
ADMIN_JWT_SECRET=long-random
ADMIN_RECOVERY_KEY=long-random
```

### Strongly recommended
```env
# Cloudflare tunnel (or other public HTTPS). PDFs + photos both use this.
# When the URL changes, update only this line and restart.
PUBLIC_BASE_URL=https://xxxx.trycloudflare.com
IMAGE_BASE_URL=
TESSERACT_CMD=/usr/bin/tesseract
DEFAULT_TENANT_ID=your-live-tenant-slug
CORS_ORIGINS=https://your-console-origin
SEND_MEDIA=true
HANDOFF_TIMEOUT_NOTIFY=0
```

### Optional
```env
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM_EMAIL=...
IMGHIPPO_API_KEY=...
GROQ_API_KEY=...
MISTRAL_API_KEY=...
EMBEDDING_MODEL_PATH=sentence-transformers/all-MiniLM-L6-v2
HKDEK_WEBHOOK_URL=...
```

---

## 7. Models downloaded at runtime (no separate “install”, but need disk/network)

| Model | Used for |
|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | FAQ / RAG embeddings |
| `BAAI/bge-reranker-base` | Reranking |
| Ollama model e.g. `qwen3:8b` | Generation / bifurcation |

First boot will download HF models unless pre-cached under the HF cache dir.

---

## 8. Directories to persist / mount

| Path | Why |
|---|---|
| `faq.db` (or `ROUTING_DB_PATH`) | All tenants, chat, FAQs, products |
| `backend/uploaded_files/` | Uploaded media/docs |
| `clients/` | Tenant config packs |
| `data/tenants/` | Bifurcated knowledge markdown |
| HF / torch cache | Avoid re-downloading models |
| Playwright browser cache | `~/.cache/ms-playwright` (Linux) |

---

## 9. Process supervisor (production)

Pick one:
- **systemd** unit for `python backend/main.py`
- **Docker** (`Dockerfile` already installs tesseract + runs port 9000)
- **nginx** reverse proxy → `127.0.0.1:9000` with HTTPS

Also run Ollama as a service if `API_PROVIDER=ollama`.

---

## 10. Post-deploy smoke checklist

1. `GET http://SERVER:9000/api/auth/status` → OK  
2. Login console → create/publish tenant  
3. Set **Active Test Tenant** (or bind `SEND2_NUMBER` / `mobile_number`)  
4. WhatsApp **Hi** → menu reply (`whatsapp_send_log` reason=`reply`)  
5. Upload a scanned PDF → confirm log shows `OCR enabled | tesseract=...`  
6. Confirm **only one** bot process is running  

---

## Quick “install order” summary

1. Python 3.11/3.12 + venv  
2. VC++ Redistributable (Windows)  
3. Tesseract OCR  
4. Node.js 20+ (frontend)  
5. Ollama + pull model **or** cloud LLM keys  
6. `pip install -r requirements.txt`  
7. `playwright install chromium` (+ Linux deps)  
8. `npm install && npm run build` (frontend)  
9. Fill `routing/.env`  
10. Start **one** `python backend/main.py`  
11. Configure Send2 + public HTTPS URL  
12. Create first admin + demo/live tenant  

`requirements.txt` is **not** enough alone — items 2–5, 7–9, and 11 are the usual missing pieces on a fresh server.
