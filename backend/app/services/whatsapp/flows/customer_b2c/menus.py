"""
B2C WhatsApp menu definitions with dynamic multi-tenant profile resolution
and Smart Switch between Quick Reply buttons (<= 3 options) and List drawers (> 3 options).
"""

import logging
from typing import Optional
from services.menu_catalog import get_kb_main_menu
from services.menu_service import MenuItem, build_list_menu, personalize_header, resolve_menu_header

logger = logging.getLogger("b2c_menus")


def get_main_menu(wa_id: str = "", tenant_id: Optional[str] = None) -> dict:
    """Dynamic main menu for B2C customers.

    1. Resolves active tenant (testing override -> request context -> user mapping -> default).
    2. Loads the tenant's published profile menu buttons.
    3. Smart Switch:
       - <= 3 active options -> returns interactive Quick Reply buttons format (single tap).
       - > 3 active options -> returns full WhatsApp List Menu drawer.
    """
    # 1. Resolve tenant (active test override beats phone binding / user stamp)
    try:
        from shared.tenancy.resolver import resolve_effective_tenant_id
        resolved_tid = resolve_effective_tenant_id(wa_id, tenant_id)
    except Exception:
        resolved_tid = str(tenant_id or "default")

    # 2. Extract tenant-specific profile menu
    items = []
    # Always from the resolved active tenant — never a frozen global brand.
    header_title = resolve_menu_header(wa_id, resolved_tid)
    body_text = "What would you like to explore today?"
    button_text = "Show Options"

    try:
        from shared.tenancy.loader import get_tenant_profile
        p = get_tenant_profile(resolved_tid)
        if p:
            if p.menu and p.menu.body:
                body_text = p.menu.body
            if p.menu and p.menu.button_text:
                button_text = str(p.menu.button_text).strip() or button_text
            if p.menu and p.menu.buttons:
                # Honor feature gates (and skip title-less kit leftovers). One
                # section keeps WhatsApp under its 3-section limit.
                visible = p.menu.visible_buttons(p.features)
                for b in visible:
                    # Plain short titles only — emoji in title gets cut on WhatsApp.
                    title = (getattr(b, "title", None) or "").strip()[:20]
                    if not title:
                        continue
                    desc = (getattr(b, "description", None) or "").strip()[:72]
                    bid = getattr(b, "id", None) or f"menu_{title.lower().replace(' ', '_')}"
                    items.append(
                        MenuItem(
                            id=bid,
                            title=title,
                            description=desc,
                            section="Options",
                            icon="",
                        )
                    )
    except Exception as e:
        logger.warning(f"Could not load profile menu for tenant '{resolved_tid}': {e}")

    # Fallback to code defaults if tenant has no buttons
    if not items:
        items = get_kb_main_menu(wa_id, tenant_id=resolved_tid)
        header_title = personalize_header(wa_id, user_type="b2c")

    logger.info(
        "MAIN_MENU | tenant=%s | n=%d | titles=%s",
        resolved_tid,
        len(items),
        [it.title for it in items[:10]],
    )

    # 3. Smart Switch
    # When 1 to 3 items exist, send high-conversion single-tap Quick Reply buttons
    if 1 <= len(items) <= 3:
        quick_buttons = []
        for it in items[:3]:
            # Never prepend icon — WhatsApp reply titles max 20 chars.
            btn_title = (it.title or "")[:20]
            quick_buttons.append({"id": it.id, "title": btn_title})
        return {
            "type": "buttons",
            "text": f"*{header_title}*\n\n{body_text}" if header_title else body_text,
            "buttons": quick_buttons,
            "tenant_id": resolved_tid,
        }

    # When > 3 items exist, render structured WhatsApp List menu (up to 10 rows)
    menu = build_list_menu(
        header=header_title[:60],
        body=body_text[:1024],
        button_text=button_text[:20],
        items=items[:10],
    )
    menu["type"] = "list"
    menu["tenant_id"] = resolved_tid
    return menu