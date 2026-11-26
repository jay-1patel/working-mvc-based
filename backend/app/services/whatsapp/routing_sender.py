import logging
import re
import requests
import httpx
from routing.config import (
    SEND2_SESSION_SEND_URL,
    SEND2_LIST_MENU_URL,
    SEND2_QUICK_BUTTON_URL,
    SEND2_LOCATION_URL,
    SEND2_AUTH_TOKEN,
)

logger = logging.getLogger("chiki_webhook")

VALID_MSG_TYPES = ("text", "image", "video", "audio", "document")


def _digits_phone(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def resolve_outbound_from_number(tenant_id: str | None = None) -> str:
    """Business line to send from: inbound display_phone_number, else tenants.waba_phone_id."""
    try:
        from database import get_request_waba_phone
        cur = _digits_phone(get_request_waba_phone() or "")
        if len(cur) >= 10:
            return cur
    except Exception:
        logger.debug("OUTBOUND_FROM_CTX_SKIP", exc_info=True)

    tid = str(tenant_id or "").strip()
    if not tid:
        try:
            from database import get_request_tenant
            tid = str(get_request_tenant() or "").strip()
        except Exception:
            tid = ""
    if not tid:
        return ""
    try:
        from shared.tenancy import store as tenancy_store
        row = tenancy_store.get_tenant(tid) or {}
        return _digits_phone(row.get("waba_phone_id") or "")
    except Exception:
        logger.debug("OUTBOUND_FROM_DB_SKIP | tenant=%s", tid, exc_info=True)
        return ""


def resolve_outbound_phone_number_id(tenant_id: str | None = None) -> str:
    """Meta Graph phone_number_id for outbound Cloud API routing (if known)."""
    try:
        from database import get_request_waba_phone_id
        cur = _digits_phone(get_request_waba_phone_id() or "")
        if len(cur) >= 10:
            return cur
    except Exception:
        logger.debug("OUTBOUND_PHONE_ID_CTX_SKIP", exc_info=True)
    # Fall back to display digits when webhook used the same value for both.
    return resolve_outbound_from_number(tenant_id)


def _with_from_number(payload: dict, tenant_id: str | None = None) -> dict:
    """Stamp Send2 payload so the reply leaves from the inbound business number.

    Send2 multi-number accounts often ignore a lone display number and fall back
    to the account primary line. Stamp every common selector Send2/Cloud accept:
    display number + Meta ``phone_number_id``.
    """
    from_no = resolve_outbound_from_number(tenant_id)
    phone_id = resolve_outbound_phone_number_id(tenant_id)
    customer = (
        payload.get("contact_no")
        or payload.get("number")
        or payload.get("to")
        or ""
    )
    if from_no or phone_id:
        if from_no:
            payload["from_number"] = from_no
            payload["display_phone_number"] = from_no
            payload["from"] = from_no
            payload["whatsapp_number"] = from_no
        if phone_id:
            payload["phone_number_id"] = phone_id
        logger.info(
            "MSG_OUT | reply_from=%s | phone_number_id=%s | customer=%s | tenant=%s | type=%s",
            from_no or "(none)",
            phone_id or "(none)",
            customer or "?",
            tenant_id or "",
            payload.get("message_type") or (
                (payload.get("interactive") or {}).get("type") if isinstance(payload.get("interactive"), dict) else None
            ) or "?",
        )
        logger.info(
            "OUTBOUND_FROM_NUMBER | from=%s | phone_number_id=%s | tenant=%s",
            from_no or "(none)", phone_id or "(none)", tenant_id or "",
        )
    else:
        logger.warning(
            "MSG_OUT | reply_from=(MISSING) | customer=%s | tenant=%s | Send2 may use account default number",
            customer or "?",
            tenant_id or "",
        )
        logger.warning("OUTBOUND_FROM_NUMBER_MISSING | tenant=%s", tenant_id or "")
    return payload


def _send2_response_ok(status_code: int, body_text: str | None) -> bool:
    """Treat common Send2 success shapes as OK.

    Some endpoints return JSON with ``success`` / ``Message Sent Successfully``;
    list + quick-button APIs often return the bare string ``OK``.
    """
    if status_code != 200:
        return False
    body = (body_text or "").strip().lower()
    if not body:
        return False
    if body in ("ok", '"ok"', "'ok'"):
        return True
    return (
        "message sent successfully" in body
        or '"success":true' in body
        or '"success": true' in body
        or '"success":1' in body
        or '"success": 1' in body
    )


def _resolve_media_url(media_url: str) -> str:
    """Make a media URL absolute under PUBLIC_BASE_URL (Cloudflare from .env).

    Relative paths and old-host ``/uploaded_files/...`` links are rebased so
    WhatsApp always fetches from the current ``routing/.env`` origin.
    """
    if not media_url:
        return media_url
    try:
        from services.media_host import rebase_public_url
    except ImportError:
        try:
            from backend.services.media_host import rebase_public_url
        except ImportError:
            rebase_public_url = None  # type: ignore
    if rebase_public_url:
        rebased = rebase_public_url(media_url)
        if rebased:
            return rebased
    if media_url.startswith(("http://", "https://")):
        return media_url
    from routing.config import PUBLIC_BASE_URL
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    if base:
        return base + "/" + media_url.lstrip("/")
    return "https://" + media_url


def _normalize_msg_type(msg_type: str) -> str:
    """Map FAQ/other media labels to the WhatsApp media types send2 accepts."""
    if not msg_type:
        return "text"
    mt = msg_type.lower()
    if mt in ("pdf", "doc", "docx", "xlsx", "csv"):
        return "document"
    if mt == "jpg":
        return "image"
    if mt == "png":
        return "image"
    if mt in VALID_MSG_TYPES:
        return mt
    return "text"


def normalize_whatsapp_formatting(text: str) -> str:
    """
    Normalize Markdown-ish emphasis, headers, links, and bullets so WhatsApp
    renders clean bold/italic (*bold* / _italic_) and clickable URLs instead of
    broken raw markdown syntax. Also formats markdown tables into clean bulleted lists.
    """
    if not text:
        return text or ""
    import re

    # 0. Strip wrapping code fences (e.g. ```json ... ``` or ```markdown ... ``` or bare ```)
    clean = text.strip()
    clean = re.sub(r"^```(?:json|markdown|text)?\s*\n?", "", clean)
    clean = re.sub(r"\n?```\s*$", "", clean)
    text = clean

    # 1. Convert markdown tables into clean WhatsApp bullet points
    lines = text.split("\n")
    table_converted = []
    in_table = False
    headers = []
    for line in lines:
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            parts = [p.strip() for p in s.strip("|").split("|")]
            # Skip separator rows like | --- | --- |
            if all(re.match(r"^:?-+:?$", p) for p in parts if p):
                continue
            if not in_table:
                headers = parts
                in_table = True
            else:
                row_items = []
                for idx, cell in enumerate(parts):
                    if not cell:
                        continue
                    if idx < len(headers) and headers[idx]:
                        row_items.append(f"*{headers[idx]}*: {cell}")
                    else:
                        row_items.append(cell)
                if row_items:
                    table_converted.append("• " + " | ".join(row_items))
        else:
            in_table = False
            headers = []
            table_converted.append(line)
    text = "\n".join(table_converted)

    # 2. Markdown headers (# Header, ## Subheading) -> WhatsApp bold (*Header*)
    text = re.sub(r"(?m)^#{1,6}\s*(.+?)\s*$", r"*\1*", text)

    # 3. Markdown links: [Title](https://...) -> Title: https://...
    def _link_repl(m):
        title = m.group(1).strip()
        url = m.group(2).strip()
        if not title or title.lower() == url.lower():
            return url
        return f"{title}: {url}"
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", _link_repl, text)

    # 4. Bold + Italic: ***text*** / ___text___ -> *_text_*
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"*_\1_*", text)
    text = re.sub(r"___(.+?)___", r"*_\1_*", text)

    # 5. Bold: **text** / __text__ -> *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)

    # 6. Strikethrough: ~~text~~ -> ~text~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)

    # 7. Asterisk bullet points at line starts (* Item) -> • Item
    # Prevents WhatsApp from pairing asterisks across lines and bolding entire lists
    text = re.sub(r"(?m)^\*\s+", r"• ", text)

    # 8. Compress 3+ consecutive newlines down to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def send_whatsapp_typing(to: str, tenant_id: str = None) -> bool:
    """Send typing indicator or mark as read if supported by provider, failing silently."""
    try:
        username, password = get_tenant_send2_credentials(tenant_id)
        if not username or not password:
            return False
        clean_to = re.sub(r"[^\d]", "", str(to or "")).strip() or str(to)
        payload = _with_from_number({
            "user_name": username,
            "password": password,
            "contact_no": clean_to,
            "message_type": "action",
            "action": "typing",
            "messaging_product": "whatsapp",
        }, tenant_id)
        requests.post(SEND2_SESSION_SEND_URL, json=payload, timeout=2)
        return True
    except Exception:
        return False


def get_tenant_send2_credentials(tenant_id: str = None) -> tuple:
    """Retrieve Send2 username/password for the given tenant.

    Order: encrypted vault → admins table → optional env only if
    SEND2_VAULT_FALLBACK=true. Decryption failures raise — never send
    garbage credentials to Send2.
    """
    try:
        from services.credential_vault import (
            CredentialVaultError,
            resolve_send2_username_password,
        )
    except ImportError:
        from backend.services.credential_vault import (
            CredentialVaultError,
            resolve_send2_username_password,
        )
    try:
        return resolve_send2_username_password(tenant_id)
    except CredentialVaultError:
        raise
    except Exception as exc:
        logger.error(
            "SEND2_CREDENTIAL_RESOLVE_FAILED | tenant=%s | error=%s",
            tenant_id,
            type(exc).__name__,
        )
        raise


def _chunk_text(text: str, limit: int = 4000) -> list:
    """Split long text into safe chunks for WhatsApp (Meta max 4096 chars)."""
    text = (text or "").strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, limit)
        if split_at == -1 or split_at < limit // 3:
            split_at = text.rfind("\n", 0, limit)
        if split_at == -1 or split_at < limit // 3:
            split_at = text.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunk = text[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        text = text[split_at:].strip()
    return chunks


def send_whatsapp_message(to, text, msg_type="text", timeout=15, retries=2, tenant_id=None):
    norm_type = _normalize_msg_type(msg_type)
    username, password = get_tenant_send2_credentials(tenant_id)
    clean_to = re.sub(r"[^\d]", "", str(to or "")).strip() or str(to)

    if norm_type == "text":
        formatted_text = normalize_whatsapp_formatting(text)
        chunks = _chunk_text(formatted_text, limit=4000)
        if not chunks:
            chunks = [" "]
        all_ok = True
        for chunk in chunks:
            payload = _with_from_number({
                "user_name": username,
                "password": password,
                "contact_no": clean_to,
                "message_type": "text",
                "message": chunk,
                "messaging_product": "whatsapp",
            }, tenant_id)
            last_err = None
            sent_chunk = False
            for attempt in range(1, retries + 1):
                try:
                    resp = requests.post(
                        SEND2_SESSION_SEND_URL,
                        json=payload,
                        timeout=timeout,
                    )
                    logger.info(
                        "MSG_OUT_RESULT | reply_from=%s | customer=%s | type=%s | status=%s | body=%s",
                        payload.get("from_number") or "(none)",
                        clean_to,
                        norm_type,
                        resp.status_code,
                        (resp.text or "")[:300],
                    )
                    from routing.hookdeck import tee_outbound
                    tee_outbound(SEND2_SESSION_SEND_URL, payload, resp.status_code, resp.text, to=clean_to)
                    if _send2_response_ok(resp.status_code, resp.text):
                        sent_chunk = True
                        break
                except Exception as e:
                    last_err = e
                    logger.warning(f"send2.digital send failed for {norm_type} (attempt {attempt}/{retries}): {e}")
            if not sent_chunk:
                from routing.hookdeck import tee_outbound
                tee_outbound(SEND2_SESSION_SEND_URL, payload, None, f"exception: {last_err}", to=clean_to)
                logger.error(f"send2.digital send failed for {norm_type} after {retries} attempts: {last_err}")
                all_ok = False
        return all_ok
    else:
        media_url = _resolve_media_url(str(text or "").strip())
        logger.info(f"MEDIA_SEND | to={to} | type={norm_type} | url={media_url[:120]}")
        payload = _with_from_number({
            "user_name": username,
            "password": password,
            "contact_no": clean_to,
            "message_type": norm_type,
            "media_url": media_url,
            "message": media_url,
            "messaging_product": "whatsapp",
        }, tenant_id)

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(
                    SEND2_SESSION_SEND_URL,
                    json=payload,
                    timeout=timeout,
                )
                logger.info(
                    "MSG_OUT_RESULT | reply_from=%s | customer=%s | type=%s | status=%s | body=%s",
                    payload.get("from_number") or "(none)",
                    clean_to,
                    norm_type,
                    resp.status_code,
                    (resp.text or "")[:300],
                )
                from routing.hookdeck import tee_outbound
                tee_outbound(SEND2_SESSION_SEND_URL, payload, resp.status_code, resp.text, to=clean_to)
                return _send2_response_ok(resp.status_code, resp.text)
            except Exception as e:
                last_err = e
                logger.warning(f"send2.digital send failed for {norm_type} (attempt {attempt}/{retries}): {e}")
        from routing.hookdeck import tee_outbound
        tee_outbound(SEND2_SESSION_SEND_URL, payload, None, f"exception: {last_err}", to=clean_to)
        logger.error(f"send2.digital send failed for {norm_type} after {retries} attempts: {last_err}")
        return False


def send_whatsapp_location(
    to,
    message: str = "",
    *,
    tenant_id=None,
    auth_token: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    name: str | None = None,
    address: str | None = None,
    timeout: int = 30,
) -> bool:
    """Send a WhatsApp location pin via Send2 ``/whatsapp/attachment/location``.

    Payload matches the Send2 location attachment API:
    username, password, message, to, authToken — plus optional lat/lng/name/address
    when the tenant brand has map coordinates.
    """
    username, password = get_tenant_send2_credentials(tenant_id)
    clean_to = re.sub(r"[^\d]", "", str(to or "")).strip() or str(to)
    token = (auth_token if auth_token is not None else SEND2_AUTH_TOKEN) or ""
    payload = _with_from_number({
        "username": username,
        "password": password,
        "message": str(message or "").strip() or " ",
        "to": clean_to,
        "authToken": token,
    }, tenant_id)
    if latitude is not None:
        payload["latitude"] = float(latitude)
    if longitude is not None:
        payload["longitude"] = float(longitude)
    if name:
        payload["name"] = str(name).strip()
    if address:
        payload["address"] = str(address).strip()

    url = SEND2_LOCATION_URL or "https://api.send2.digital/whatsapp/attachment/location"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        logger.info(
            "LOCATION_SEND | to=%s | status=%s | body=%s",
            clean_to, resp.status_code, (resp.text or "")[:300],
        )
        from routing.hookdeck import tee_outbound
        tee_outbound(url, payload, resp.status_code, resp.text, to=clean_to)
        return _send2_response_ok(resp.status_code, resp.text)
    except Exception as exc:
        logger.error("LOCATION_SEND_FAILED | to=%s | error=%s", clean_to, exc)
        try:
            from routing.hookdeck import tee_outbound
            tee_outbound(url, payload, None, f"exception: {exc}", to=clean_to)
        except Exception:
            pass
        return False


def send_whatsapp_list_menu(to, header_text, body_text, button_text, sections, footer_text=None, tenant_id=None):
    username, password = get_tenant_send2_credentials(tenant_id)
    clean_to = re.sub(r"[^\d]", "", str(to or "")).strip() or str(to)
    # Enforce WhatsApp / Send2 character limits:
    # row title <= 24, row desc <= 72, section title <= 24, button <= 20
    api_sections = []
    seen_row_ids: set = set()
    for section in sections:
        api_section = {
            "title": str(section.get("title", "") or "")[:24],
            "rows": []
        }
        for row in section.get("rows", []):
            rid = str(row.get("id", "") or "")[:200]
            if not rid:
                continue
            # WhatsApp rejects the whole list when two rows share an id.
            base = rid
            n = 2
            while rid in seen_row_ids:
                suffix = f"_{n}"
                rid = (base[: 200 - len(suffix)] + suffix)
                n += 1
            seen_row_ids.add(rid)
            api_row = {
                "id": rid,
                "title": str(row.get("title", "") or "")[:24],
                "description": str(row.get("description", "") or "")[:72],
            }
            api_section["rows"].append(api_row)
        if api_section["rows"]:
            api_sections.append(api_section)

    if not api_sections:
        logger.warning("LIST_MENU_SKIP | to=%s | no rows", to)
        return False

    # WhatsApp rejects the whole message when the body is empty or > 1024 chars
    # ("Body text length invalid. Min length: 1, Max length: 1024").
    # If the body is long (> 950 chars), deliver the FULL untruncated content
    # first via text message, and present the menu with a clean prompt.
    raw_body = normalize_whatsapp_formatting(body_text or " ")
    if len(raw_body) > 950:
        logger.info(f"LIST_MENU_SPLIT | to={to} | chars={len(raw_body)} | sending full text first")
        send_whatsapp_message(to, body_text, tenant_id=tenant_id)
        norm_body = "Please select an option below:"
    else:
        norm_body = _truncate_body(raw_body, limit=1020)

    btn = str(button_text or "Menu")[:20]
    header = str(header_text or "").strip()[:60]
    footer = str(footer_text or " ").strip()[:60] or " "
    row_count = sum(len(s.get("rows", [])) for s in api_sections)

    # Primary: session-msg-send Cloud interactive list (same path as working text).
    # The legacy list_messages endpoint often returns bare "OK" without delivery.
    cloud_interactive = {
        "type": "list",
        "body": {"text": norm_body or " "},
        "footer": {"text": footer},
        "action": {"button": btn, "sections": api_sections},
    }
    if header:
        cloud_interactive["header"] = {"type": "text", "text": header}
    cloud_payload = _with_from_number({
        "user_name": username,
        "password": password,
        "contact_no": clean_to,
        "message_type": "interactive",
        "interactive": cloud_interactive,
        "messaging_product": "whatsapp",
    }, tenant_id)
    try:
        logger.info(
            "LIST_MENU_CLOUD_REQUEST | to=%s | sections=%d | rows=%d | from=%s",
            clean_to, len(api_sections), row_count,
            cloud_payload.get("from_number") or "",
        )
        with httpx.Client(trust_env=False, timeout=30) as client:
            resp = client.post(SEND2_SESSION_SEND_URL, json=cloud_payload)
        logger.info(
            "LIST_MENU_CLOUD_RESPONSE | to=%s | status=%s | body=%s",
            clean_to, resp.status_code, (resp.text or "")[:300],
        )
        from routing.hookdeck import tee_outbound
        tee_outbound(SEND2_SESSION_SEND_URL, cloud_payload, resp.status_code, resp.text, to=clean_to)
        low = (resp.text or "").lower()
        if (
            _send2_response_ok(resp.status_code, resp.text)
            and "invalid parameter" not in low
            and "interactive payload is required" not in low
        ):
            return True
        logger.warning("LIST_MENU_CLOUD_FALLBACK | to=%s | trying legacy list_messages", clean_to)
    except Exception as e:
        logger.warning("LIST_MENU_CLOUD_FAILED | to=%s | error=%s | trying legacy", clean_to, e)

    payload = _with_from_number({
        "username": username,
        "password": password,
        "number": clean_to,
        "headertext": header or " ",
        "bodytext": norm_body or " ",
        "footertext": footer,
        "buttontext": btn,
        "total_number_section": len(api_sections),
        "total_rows": row_count,
        "sections": api_sections,
    }, tenant_id)
    try:
        logger.info(f"LIST_MENU_REQUEST | to={clean_to} | sections={len(api_sections)} | rows={row_count}")
        with httpx.Client(trust_env=False, timeout=30) as client:
            resp = client.post(SEND2_LIST_MENU_URL, json=payload)
        logger.info(f"LIST_MENU_RESPONSE | to={clean_to} | status={resp.status_code} | body={resp.text[:300]}")
        from routing.hookdeck import tee_outbound
        tee_outbound(SEND2_LIST_MENU_URL, payload, resp.status_code, resp.text, to=clean_to)
        # Bare "OK" from this endpoint is unreliable — require an explicit success phrase.
        body = (resp.text or "").strip().lower()
        if resp.status_code == 200 and (
            "message sent successfully" in body
            or '"success":true' in body
            or '"success": true' in body
        ):
            return True
        logger.error(
            "LIST_MENU_UNRELIABLE_OK | to=%s | status=%s | body=%s",
            clean_to, resp.status_code, (resp.text or "")[:200],
        )
        return False
    except Exception as e:
        logger.error(f"send2.digital list menu send failed: {e}")
        return False


def format_list_menu_as_text(body_text, sections, footer_text=None) -> str:
    """Numbered text version of a list menu (reliable session-msg-send fallback)."""
    text = (body_text or "").rstrip() + "\n\n"
    count = 0
    for sec in (sections or [])[:8]:
        title = (sec.get("title") or "").strip()
        if title:
            text += f"*{title}*\n"
        for row in (sec.get("rows") or [])[:10]:
            count += 1
            row_title = (row.get("title") or "").strip() or f"Option {count}"
            desc = (row.get("description") or "").strip()
            text += f"{count}. {row_title}"
            if desc:
                text += f" — {desc[:60]}"
            text += "\n"
            if count >= 20:
                break
        if count >= 20:
            break
    if count:
        text += f"\nReply with a number (*1*-*{count}*)"
    if footer_text:
        text += f"\n_{footer_text}_"
    return text.strip()


def _truncate_body(text: str, limit: int = 1020) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_space = cut.rfind(" ")
    if last_space > limit // 2:
        cut = cut[:last_space]
    return cut.rstrip()


def send_whatsapp_cta_url(
    to: str,
    body_text: str,
    cta_url: str,
    display_text: str = "Learn More",
    image_url: str = None,
    footer_text: str = None,
    tenant_id: str = None,
    timeout: int = 60,
) -> bool:
    """Send send2 interactive ``cta_url`` with optional image header.

    Notes from send2:
    - Do not mix reply buttons with CTA URL in one payload.
    - Max 1 CTA URL button per interactive payload.
    - Image goes in ``interactive.header`` (type=image).
    """
    username, password = get_tenant_send2_credentials(tenant_id)
    clean_to = re.sub(r"[^\d]", "", str(to or "")).strip() or str(to)
    url = str(cta_url or "").strip()
    if not url.startswith(("http://", "https://")):
        logger.error("CTA_URL_INVALID | to=%s | url=%r", to, url)
        return False

    body = _truncate_body(normalize_whatsapp_formatting(body_text or " ") or " ", limit=1020)
    label = str(display_text or "Learn More").strip()[:20] or "Learn More"
    footer = str(footer_text or " ").strip() or " "

    interactive = {
        "type": "cta_url",
        "body": {"text": body},
        "footer": {"text": footer[:60]},
        "action": {
            "name": "cta_url",
            "parameters": {
                "display_text": label,
                "url": url,
            },
        },
    }

    image_link = str(image_url or "").strip()
    if image_link:
        try:
            from kb.services.whatsapp import resolve_public_media_url
            resolved = resolve_public_media_url(image_link)
            if resolved:
                image_link = resolved
        except Exception:
            image_link = _resolve_media_url(image_link)
        if image_link.startswith(("http://", "https://")):
            interactive["header"] = {
                "type": "image",
                "image": {"link": image_link},
            }

    payload = _with_from_number({
        "user_name": username,
        "password": password,
        "contact_no": clean_to,
        "message_type": "interactive",
        "interactive": interactive,
    }, tenant_id)
    try:
        logger.info(
            "CTA_URL_REQUEST | to=%s | has_image=%s | display=%r | url=%s",
            to, "header" in interactive, label, url[:120],
        )
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            resp = client.post(SEND2_SESSION_SEND_URL, json=payload)
        logger.info(
            "CTA_URL_RESPONSE | to=%s | status=%s | body=%s",
            to, resp.status_code, (resp.text or "")[:300],
        )
        try:
            from routing.hookdeck import tee_outbound
            tee_outbound(SEND2_SESSION_SEND_URL, payload, resp.status_code, resp.text, to=clean_to)
        except Exception:
            # deliberate: the outbound tee is an observability side-channel;
            # its failure must never affect the actual send.
            logger.debug("TEE_OUTBOUND_FAILED | to=%s", clean_to, exc_info=True)
        return _send2_response_ok(resp.status_code, resp.text)
    except Exception as e:
        logger.error("CTA_URL_FAILED | to=%s | error=%s", to, e)
        return False


def normalize_reply_buttons(buttons):
    """Coerce incoming buttons into send2.digital's interactive button shape.

    Callers hand us buttons in two shapes: already-formatted
    ``{"type": "reply", "reply": {"id", "title"}}`` (what the bot workflows
    emit) or flat ``{"id", "title"}``. send2.digital / WhatsApp reject the
    entire message when ``reply.id`` is empty, so any button missing an id or a
    title is dropped rather than sent half-formed.
    """
    out = []
    for btn in buttons or []:
        if not isinstance(btn, dict):
            continue
        reply = btn.get("reply")
        if isinstance(reply, dict):
            bid = reply.get("id") or btn.get("id")
            title = reply.get("title") or btn.get("title")
        else:
            bid = btn.get("id")
            title = btn.get("title")
        bid = str(bid).strip() if bid is not None else ""
        title = str(title).strip() if title is not None else ""
        if bid and title:
            out.append({"type": "reply", "reply": {"id": bid, "title": title}})
    return out


def send_whatsapp_interactive(to, text, buttons, footer=None, tenant_id=None):
    """Send an interactive button message via send2.digital.

    Primary path is ``session-msg-send`` Cloud interactive (same as working
    text / list menus). The legacy quick-button endpoint often returns bare
    ``OK`` without delivering to WhatsApp, so it is only a fallback and bare
    ``OK`` there is treated as failure (caller can fall back to plain text).

    `buttons` is a list of button objects in the send2.digital format, e.g.:
        [{"type": "reply", "reply": {"id": "check_moq", "title": "Check MOQ by product"}}]
    """
    username, password = get_tenant_send2_credentials(tenant_id)
    clean_to = re.sub(r"[^\d]", "", str(to or "")).strip() or str(to)
    buttons = normalize_reply_buttons(buttons)
    if not buttons:
        logger.warning("No usable buttons for interactive message (missing id/title)")
        return False

    if len(buttons) > 3:
        logger.warning(f"Too many buttons ({len(buttons)}), limiting to 3")
        buttons = buttons[:3]

    # Enforce button title limit (WhatsApp max 20 chars)
    formatted_buttons = []
    for btn in buttons:
        if isinstance(btn, dict):
            b_copy = dict(btn)
            if "reply" in b_copy and isinstance(b_copy["reply"], dict):
                r_copy = dict(b_copy["reply"])
                r_copy["title"] = str(r_copy.get("title", ""))[:20]
                b_copy["reply"] = r_copy
            formatted_buttons.append(b_copy)
        else:
            formatted_buttons.append(btn)

    raw_text = normalize_whatsapp_formatting(text or " ")
    if len(raw_text) > 950:
        logger.info(f"INTERACTIVE_SPLIT | to={to} | chars={len(raw_text)} | sending full text first")
        send_whatsapp_message(to, text, tenant_id=tenant_id)
        body_to_send = "Please select an option below:"
    else:
        body_to_send = _truncate_body(raw_text, limit=1020) or " "

    footer_text = str(footer or " ").strip()[:60] or " "

    # Primary: session-msg-send Cloud interactive buttons (reliable delivery).
    cloud_interactive = {
        "type": "button",
        "body": {"text": body_to_send},
        "footer": {"text": footer_text},
        "action": {"buttons": formatted_buttons},
    }
    cloud_payload = _with_from_number({
        "user_name": username,
        "password": password,
        "contact_no": clean_to,
        "message_type": "interactive",
        "interactive": cloud_interactive,
        "messaging_product": "whatsapp",
    }, tenant_id)
    try:
        logger.info(
            "INTERACTIVE_CLOUD_REQUEST | to=%s | buttons=%d | from=%s",
            clean_to, len(formatted_buttons),
            cloud_payload.get("from_number") or "",
        )
        with httpx.Client(trust_env=False, timeout=30) as client:
            resp = client.post(SEND2_SESSION_SEND_URL, json=cloud_payload)
        logger.info(
            "INTERACTIVE_CLOUD_RESPONSE | to=%s | status=%s | body=%s",
            clean_to, resp.status_code, (resp.text or "")[:300],
        )
        from routing.hookdeck import tee_outbound
        tee_outbound(SEND2_SESSION_SEND_URL, cloud_payload, resp.status_code, resp.text, to=clean_to)
        low = (resp.text or "").lower()
        if (
            _send2_response_ok(resp.status_code, resp.text)
            and "invalid parameter" not in low
            and "interactive payload is required" not in low
            and "unexpected server error" not in low
        ):
            return True
        logger.warning(
            "INTERACTIVE_CLOUD_FALLBACK | to=%s | trying legacy quick-button",
            clean_to,
        )
    except Exception as e:
        logger.warning(
            "INTERACTIVE_CLOUD_FAILED | to=%s | error=%s | trying legacy quick-button",
            clean_to, e,
        )

    # Fallback: Quick Button endpoint. Bare "OK" is unreliable — require an
    # explicit success phrase (same policy as list_messages).
    # NOTE: headertext and footertext must be NON-EMPTY strings, otherwise
    # send2.digital rejects the whole request with {"error":"INVALID PARAMETER"}.
    payload = _with_from_number({
        "username": username,
        "password": password,
        "number": clean_to,
        "headertype": "text",
        "headertext": " ",
        "bodytext": body_to_send,
        "footertext": footer_text,
        "total_buttons": len(formatted_buttons),
        "buttons": formatted_buttons,
    }, tenant_id)
    try:
        resp = requests.post(
            SEND2_QUICK_BUTTON_URL,
            json=payload,
            timeout=30,
        )
        logger.info(
            "Interactive reply sent to %s, status=%s, body=%s",
            clean_to, resp.status_code, (resp.text or "")[:300],
        )
        from routing.hookdeck import tee_outbound
        tee_outbound(SEND2_QUICK_BUTTON_URL, payload, resp.status_code, resp.text, to=clean_to)
        body = (resp.text or "").strip().lower()
        if resp.status_code == 200 and (
            "message sent successfully" in body
            or '"success":true' in body
            or '"success": true' in body
        ):
            return True
        logger.error(
            "INTERACTIVE_QUICKBTN_UNRELIABLE_OK | to=%s | status=%s | body=%s",
            clean_to, resp.status_code, (resp.text or "")[:200],
        )
        return False
    except Exception as e:
        logger.error(f"send2.digital interactive send failed: {e}")
        return False
