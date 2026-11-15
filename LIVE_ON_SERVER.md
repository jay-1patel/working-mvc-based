# Make this live on a server — main checklist

One-page list of everything required to run the WhatsApp chatbot in production.
Detail reference: `DEPLOYMENT_REQUIREMENTS.md`.

---

## 1. Server hardware

| Item | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04+ (preferred) or Windows Server | Ubuntu 22.04+ |
| CPU | 4 cores | 8+ cores (if local Ollama) |
| RAM | 16 GB | 32 GB (Ollama + embeddings) |
| Disk | 40 GB free | 80 GB+ |
| Rule | **One** `python backend/main.py` process only | Two processes = double WhatsApp replies |

---

## 2. Software to install on the server

| # | Thing | Why |
|---|---|---|
| 1 | **Python 3.11 or 3.12** + venv | App runtime (avoid 3.15 — FAISS breaks) |
| 2 | **Node.js 20+** + npm | Build Tenant Console (`frontend/`) |
| 3 | **Tesseract OCR** | Scanned / image PDFs |
| 5 | **Playwright Chromium** | Website crawl |
| 6 | **nginx** (or similar) | HTTPS reverse proxy → port 9000 |
| 8 | VC++ Redistributable | **Windows only** — PyTorch DLLs |

### Quick install order
```bash
# 1) Python deps
cd mvc-based-code-main
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
# Linux also: python -m playwright install-deps chromium

# 2) Frontend production build
cd frontend && npm install && npm run build && cd ..

# 3) Ollama (if local LLM)
# install from https://ollama.com  then:
ollama pull qwen3:8b

# 4) OCR
# Ubuntu: sudo apt-get install -y tesseract-ocr
```

---

## 3. Accounts / external services (must have)

| Service | Needed for |
|---|---|
| **Send2.digital** | Live WhatsApp send/receive (username, password, business number) |
| **Public HTTPS URL** | Cloudflare Tunnel / ngrok / real domain → media + webhooks (`PUBLIC_BASE_URL`) |
| **LLM** | Ollama on server **or** Groq/Mistral API keys |
| **ImgHippo** (optional) | Host images for WhatsApp media |
| **SMTP** (optional) | Admin OTP / password reset emails |
| **Hookdeck** (optional) | Mirror Meta/WhatsApp webhooks to your server |

---

## 4. Environment (`routing/.env`) — main keys

Copy `routing/.env`, then set these for production (never commit real secrets).

### WhatsApp (Send2)
```env
SEND2_USERNAME=...
SEND2_PASSWORD=...
SEND2_NUMBER=...
SEND2_SESSION_MSG_URL=https://api.send2.digital/devdesk/session-msg-send
SEND2_INCOMING_URL=https://api.send2.digital/devdesk/incoming-report
SEND2_INCOMING_ENTRY_URL=https://api.send2.digital/devdesk/AI_chatbot_API_incomingentry
SEND2_LIST_MENU_URL=https://api.send2.digital/whatsapp/attachment/list_messages
SEND2_QUICK_BUTTON_URL=https://api.send2.digital/whatsapp/attachment/session_msg_quickbtn
SEND2_MEDIA_URL=https://api.send2.digital/devdesk/media
# Use webhook path (Hookdeck/Meta → POST /webhook): keep poller off
SEND2_POLLER_ENABLED=0
WHATSAPP_VERIFY_TOKEN=change-me
```

### Public URL + media
```env
PUBLIC_BASE_URL=https://your-real-https-domain
IMAGE_BASE_URL=https://your-real-https-domain
SEND_MEDIA=true
IMGHIPPO_API_KEY=...
CORS_ORIGINS=https://your-real-https-domain
```

### Database + tenant
```env
ROUTING_DB_PATH=C:\Users\admin\Desktop\whatsapp-chatbot\mvc-based-code-main\faq.db
DEFAULT_TENANT_ID=your-live-tenant-slug
```

### Admin security (change all defaults)
```env
ADMIN_SECRET_KEY=long-random-string
ADMIN_JWT_SECRET=long-random-string
ADMIN_RECOVERY_KEY=long-random-string
ADMIN_JWT_EXPIRY_HOURS=24
```

### LLM
```env
API_PROVIDER=ollama
# Do NOT set BIFURCATE_PROVIDER=qwen on the server — that is local-dev only.
BIFURCATE_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=qwen3:8b
# If Windows CUDA crashes bifurcation: use 0. On healthy Linux GPU: 99
OLLAMA_NUM_GPU=99
BIFURCATE_OLLAMA_NUM_GPU=99
BIFURCATE_OLLAMA_TIMEOUT=300
```

### OCR
```env
TESSERACT_CMD=/usr/bin/tesseract
# Windows example:
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## 5. Ports & firewall

| Port | Open? | Service |
|---|---|---|
| **443 / 80** | Public | nginx HTTPS |
| **9000** | Local / proxy only | FastAPI bot |
| **11434** | Localhost only | Ollama |

Outbound HTTPS needed to: `api.send2.digital`, Hugging Face (first model download), Groq/Mistral/ImgHippo/SMTP if used.

---

## 6. Data folders to keep / back up

| Path | What it holds |
|---|---|
| `faq.db` (`ROUTING_DB_PATH`) | Tenants, chats, FAQs, products |
| `backend/uploaded_files/` | Uploaded PDFs / media |
| `clients/` | Tenant config packs |
| `data/tenants/` | Bifurcated knowledge |
| HF / Ollama model cache | Avoid re-download after reboot |

---

## 7. Start the app (production)

```bash
source .venv/bin/activate
python backend/main.py
# listens on 0.0.0.0:9000
```

- Put **nginx** in front with HTTPS → `127.0.0.1:9000`
- Run under **systemd** (or Docker) so it restarts on reboot
- If using Ollama: run Ollama as a service too
- Create first admin once: console first-admin setup or `POST /api/auth/first-admin`

Docker alternative: project `Dockerfile` exposes 9000 and installs Tesseract; mount `faq.db` + uploads as volumes.

---

## 8. Go-live smoke test

- [ ] `GET https://YOUR_DOMAIN/api/auth/status` → OK  
- [ ] Admin login works  
- [ ] Create / publish tenant + set **Active Test Tenant** (or bind `SEND2_NUMBER`)  
- [ ] Upload PDF → bifurcation extracts offerings/FAQs (check logs for `OLLAMA_BIFURCATION_SUCCESS`)  
- [ ] WhatsApp **Hi** → bot replies with menu  
- [ ] Media / catalogue links use `PUBLIC_BASE_URL` (not localhost)  
- [ ] Confirm **only one** bot process is running  
- [ ] Backup `faq.db` scheduled  

---

## 9. Common production failures

| Symptom | Fix |
|---|---|
| Double WhatsApp replies | Two bot processes sharing one `faq.db` — stop the extra one |
| Bifurcation empty / Ollama 500 CUDA | Set `OLLAMA_NUM_GPU=0` or fix NVIDIA drivers |
| Upload OK but no FAQ/offerings | Ollama down or crashed — check `ollama serve` + logs |
| WhatsApp no reply | Wrong Send2 URLs, poller/webhook conflict, or `DEFAULT_TENANT_ID` wrong |
| Media broken on phone | `PUBLIC_BASE_URL` must be public HTTPS, not `127.0.0.1` |
| Blank DB / missing tables | `ROUTING_DB_PATH` points to wrong file |

---

## 10. Main things summary (print this)

1. Server: 16GB+ RAM, Ubuntu preferred  
2. Install: Python 3.11/3.12, Node 20, Tesseract, Ollama (or cloud LLM), Playwright, nginx  
3. `pip install -r requirements.txt` + `npm run build`  
4. Fill `routing/.env` (Send2, secrets, public HTTPS, DB path, LLM)  
5. One bot process on port 9000 behind HTTPS  
6. Create admin + live tenant + bind WhatsApp number  
7. Smoke-test WhatsApp Hi + PDF bifurcation  
8. Back up `faq.db` and upload folders  

`pip install -r requirements.txt` alone is **not** enough — Send2, public URL, Ollama/LLM, Tesseract, and frontend build are the usual missing pieces.
