from fastapi import APIRouter, Depends
from routing.config import WHATSAPP_VERIFY_TOKEN, SEND2_USERNAME, SEND2_PASSWORD, SEND2_NUMBER
from database import clear_webhook_logs, get_webhook_stats, list_webhook_logs
import logging

from routes.auth import require_super_admin

logger = logging.getLogger("chiki_webhook")
router = APIRouter(prefix="/webhook")


@router.get("/logs")
def get_webhook_logs(
    limit: int = 50,
    direction: str = None,
    current_admin: dict = Depends(require_super_admin),
):
    return list_webhook_logs(limit=limit, direction=direction)


@router.delete("/logs")
def clear_webhook_logs_endpoint(current_admin: dict = Depends(require_super_admin)):
    clear_webhook_logs()
    return {"status": "logs cleared"}


@router.get("/status")
def webhook_status():
    """Public status endpoint — never leaks secrets (see BUG-06 / M6)."""
    return {
        "webhook_url": "/webhook",
        "verify_token_set": bool(WHATSAPP_VERIFY_TOKEN),
        "api_provider": "send2.digital",
        "send2_config": {
            "username_set": bool(SEND2_USERNAME),
            "password_set": bool(SEND2_PASSWORD),
            "number_set": bool(SEND2_NUMBER),
        },
        "routing": "FAQ Assistant + Knowledge Base Assistant (single webhook)",
        "setup": {
            "step_1": "Login to https://cpaas.send2.digital/whatsapp/dev_desk",
            "step_2": "Set Webhook URL to: https://<your-domain>/webhook",
            "step_3": "Fill SEND2_USERNAME, SEND2_PASSWORD, SEND2_NUMBER in .env",
            "step_4": "Start server: python main.py",
            "step_5": "Test via POST /test-message",
        },
    }


@router.get("/health")
def health_check(current_admin: dict = Depends(require_super_admin)):
    """Report whether messaging credentials are configured.

    This does not call Send2. Posting the username and password to a health
    URL is itself a credential use, and an unauthenticated caller must not
    be able to trigger it.
    """
    configured = bool(SEND2_USERNAME and SEND2_PASSWORD and SEND2_NUMBER)
    return {
        "all_healthy": configured,
        "services": {
            "send2_api": {
                "configured": configured,
                "ok": configured,
            },
        },
    }


@router.get("/logs/stats")
def webhook_logs_stats(current_admin: dict = Depends(require_super_admin)):
    return get_webhook_stats()