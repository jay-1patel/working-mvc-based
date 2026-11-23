"""Build Excel API map for Profile / Profile menu / WhatsApp menu pages."""
from __future__ import annotations

import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_EXPORTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)
OUT = os.path.join(_EXPORTS, "profile_whatsapp_menu_apis.xlsx")
OUT_ALT = os.path.join(_EXPORTS, "profile_whatsapp_menu_apis_v2.xlsx")

HEADERS = [
    "Page",
    "UI action / where used",
    "Method",
    "API endpoint",
    "Description",
    "Curl (Windows cmd)",
]

ROWS = [
    [
        "Profile (brand)",
        "Open Profile page — load company brand & contact fields",
        "POST",
        "/api/admin/tenants/{tenant_id}/detail",
        "Loads tenant layers, effective profile, draft banner (has_draft). Vocabulary, guardrails, and notifications.brochure_url are scrubbed from the response.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/detail" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  -d "{}"',
    ],
    [
        "Profile (brand)",
        "Save draft (super admin)",
        "POST",
        "/api/admin/tenants/{tenant_id}/profile",
        "Writes brand/contact snapshot into the working draft only. Does not change the live bot. Incoming vocabulary/guardrails/brochure_url are stripped.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/profile" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"snapshot\\":{\\"brand\\":{\\"name\\":\\"Apex Horizon Automotive LLP\\",\\"bot_name\\":\\"Horizon Concierge\\",\\"tagline\\":\\"Multi-brand cars\\",\\"website\\":\\"https://www.apexhorizonmotors.in\\",\\"support_email\\":\\"care@apexhorizonmotors.in\\",\\"support_phone\\":\\"+91 98220 44120\\",\\"signature\\":\\"Apex Horizon Motors Pune\\"}}}"',
    ],
    [
        "Profile (brand)",
        "Save & publish / Submit for approval — step 1 (always save draft first)",
        "POST",
        "/api/admin/tenants/{tenant_id}/profile",
        "Same as Save draft: always save snapshot first, then call publish.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/profile" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"snapshot\\":{\\"brand\\":{\\"name\\":\\"Apex Horizon Automotive LLP\\",\\"bot_name\\":\\"Horizon Concierge\\",\\"tagline\\":\\"Multi-brand cars\\",\\"website\\":\\"https://www.apexhorizonmotors.in\\",\\"support_email\\":\\"care@apexhorizonmotors.in\\",\\"support_phone\\":\\"+91 98220 44120\\",\\"signature\\":\\"Apex Horizon Motors Pune\\"}}}"',
    ],
    [
        "Profile (brand)",
        "Save & publish / Submit for approval — step 2",
        "POST",
        "/api/admin/tenants/{tenant_id}/publish",
        "Validates draft and publishes (or queues pending_approval for non-super admins). Live bot updates only after publish/approval.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/publish" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Accept: application/json"',
    ],
    [
        "Profile menu",
        "Open Profile menu page — load hours & notification emails",
        "POST",
        "/api/admin/tenants/{tenant_id}/detail",
        "Same detail API as Profile brand page; UI shows business_hours and notifications (no brochure_url).",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/detail" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  -d "{}"',
    ],
    [
        "Profile menu",
        "Save draft (super admin)",
        "POST",
        "/api/admin/tenants/{tenant_id}/profile",
        "Saves business_hours + notifications (sales_email, support_email) into the draft.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/profile" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"snapshot\\":{\\"business_hours\\":{\\"timezone\\":\\"Asia/Kolkata\\",\\"always_open\\":false,\\"open\\":\\"09:30\\",\\"close\\":\\"19:00\\",\\"open_days\\":[\\"mon\\",\\"tue\\",\\"wed\\",\\"thu\\",\\"fri\\",\\"sat\\"],\\"out_of_hours_message\\":\\"We are currently closed.\\"},\\"notifications\\":{\\"sales_email\\":\\"sales@apexhorizonmotors.in\\",\\"support_email\\":\\"care@apexhorizonmotors.in\\"}}}"',
    ],
    [
        "Profile menu",
        "Save & publish / Submit for approval — step 1 then step 2",
        "POST",
        "/api/admin/tenants/{tenant_id}/profile then /publish",
        "1) Save hours/notifications draft. 2) Publish (or submit for approval).",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/profile" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  --data-raw "{\\"snapshot\\":{\\"business_hours\\":{\\"timezone\\":\\"Asia/Kolkata\\",\\"always_open\\":false,\\"open\\":\\"09:30\\",\\"close\\":\\"19:00\\",\\"open_days\\":[\\"mon\\",\\"tue\\",\\"wed\\",\\"thu\\",\\"fri\\",\\"sat\\"],\\"out_of_hours_message\\":\\"We are currently closed.\\"},\\"notifications\\":{\\"sales_email\\":\\"sales@apexhorizonmotors.in\\",\\"support_email\\":\\"care@apexhorizonmotors.in\\"}}}"\n\n'
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/publish" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Accept: application/json"',
    ],
    [
        "WhatsApp menu (Bot menu)",
        "Open page — load published menu customers see",
        "POST",
        "/api/admin/tenants/resolved",
        "Returns the live published profile the bot uses (menu buttons, body text, version). Used for the Published menu list and phone preview.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/resolved" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  -d "{}"',
    ],
    [
        "WhatsApp menu (Bot menu)",
        "Draft banner + source chips (Typed by admin / system default)",
        "POST",
        "/api/admin/tenants/{tenant_id}/detail",
        "has_draft drives the yellow draft banner. Layer data is used client-side to label each button source (e.g. Typed by admin).",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/detail" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  -d "{}"',
    ],
    [
        "WhatsApp menu (Bot menu)",
        "Edit pencil / Edit in Menu editor",
        "—",
        "Navigates to Menu editor (no API)",
        "Opens /tenants/{id}/menu-edit (optionally ?focus=<button_id>). No API until Save & publish in Menu editor.",
        "(no curl — UI navigation only)",
    ],
    [
        "Menu editor (from WhatsApp menu)",
        "Open Menu editor — load draft/effective menu for editing",
        "POST",
        "/api/admin/tenants/{tenant_id}/detail",
        "Loads pending/effective menu into the editor. Add/Edit/Delete/Active-Inactive are local until Save & publish.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/detail" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  -d "{}"',
    ],
    [
        "Menu editor (from WhatsApp menu)",
        "Add option / Edit / Delete / Active-Inactive",
        "—",
        "No API (local UI state)",
        "Changes stay in the browser until Save & publish. Deletes are sent later as {id, __remove__: true} tombstones.",
        "(no curl — local only)",
    ],
    [
        "Menu editor (from WhatsApp menu)",
        "Save & publish — optional new intent pages first",
        "POST",
        "/api/admin/tenants/{tenant_id}/intents/{intent_name}",
        "If an option points at a new/edited intent page, each referenced intent is saved into the draft before the menu snapshot.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/intents/offerings" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"answer\\":\\"Here are our cars...\\",\\"keywords\\":[\\"cars\\",\\"models\\"],\\"enabled\\":true}"',
    ],
    [
        "Menu editor (from WhatsApp menu)",
        "Save & publish — step 1 save menu draft",
        "POST",
        "/api/admin/tenants/{tenant_id}/profile",
        "Saves menu snapshot (buttons, header/body/footer). Deleted ids included as __remove__ tombstones.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/profile" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"snapshot\\":{\\"menu\\":{\\"key\\":\\"main\\",\\"header\\":\\"Apex Horizon Automotive LLP\\",\\"body\\":\\"Welcome! How can we assist you today?\\",\\"footer\\":\\"Select an option or type your query directly\\",\\"button_text\\":\\"Select Option\\",\\"buttons\\":[{\\"id\\":\\"browse_offerings\\",\\"title\\":\\"Our Cars\\",\\"description\\":\\"Sedan, SUV, compact & more\\",\\"section\\":\\"Cars\\",\\"sort_order\\":0,\\"enabled\\":true},{\\"id\\":\\"book_callback\\",\\"title\\":\\"Book Test Drive\\",\\"description\\":\\"Free test drive at showroom or home\\",\\"section\\":\\"Sales\\",\\"sort_order\\":1,\\"enabled\\":true}]}}}"',
    ],
    [
        "Menu editor (from WhatsApp menu)",
        "Save & publish — step 2 publish",
        "POST",
        "/api/admin/tenants/{tenant_id}/publish",
        "Publishes the draft menu live (menu-only edits may publish without approval for tenant admins).",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/c/publish" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Accept: application/json"',
    ],
    [
        "Website crawler / Files",
        "Preview file (eye icon on file row)",
        "POST",
        "/api/admin/tenants/files/preview",
        "Returns the file bytes for in-browser preview. Body: filename.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/files/preview" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"filename\\":\\"Automobile-WhatsApp-Assistant-Company-Document.pdf\\"}" ^\n'
        "  --output preview_out.bin",
    ],
    [
        "Website crawler / Files",
        "Download file (download icon on file row)",
        "POST",
        "/api/admin/tenants/files/download",
        "Downloads the file as an attachment. Body: filename.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/files/download" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"filename\\":\\"Automobile-WhatsApp-Assistant-Company-Document.pdf\\"}" ^\n'
        '  --output "Automobile-WhatsApp-Assistant-Company-Document.pdf"',
    ],
    [
        "Website crawler / Files",
        "Delete file (trash icon on file row)",
        "POST",
        "/api/admin/tenants/files/delete",
        "Deletes the uploaded file and its indexed FAQ/KB chunks. Body: filename.",
        'curl -X POST "http://192.168.0.122:9000/api/admin/tenants/files/delete" ^\n'
        '  -H "username: cars" ^\n'
        '  -H "session_id: <TOKEN>" ^\n'
        '  -H "Content-Type: application/json" ^\n'
        '  -H "Accept: application/json" ^\n'
        '  --data-raw "{\\"filename\\":\\"Automobile-WhatsApp-Assistant-Company-Document.pdf\\"}"',
    ],
]

PAGE_FILLS = {
    "Profile (brand)": PatternFill("solid", fgColor="D6EAF8"),
    "Profile menu": PatternFill("solid", fgColor="D5F5E3"),
    "WhatsApp menu (Bot menu)": PatternFill("solid", fgColor="FCF3CF"),
    "Menu editor (from WhatsApp menu)": PatternFill("solid", fgColor="F5CBA7"),
    "Website crawler / Files": PatternFill("solid", fgColor="E8DAEF"),
}


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "API Map"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Border(
        left=Side(style="thin", color="BFBFBF"),
        right=Side(style="thin", color="BFBFBF"),
        top=Side(style="thin", color="BFBFBF"),
        bottom=Side(style="thin", color="BFBFBF"),
    )
    wrap = Alignment(wrap_text=True, vertical="top")

    ws.append(HEADERS)
    for col in range(1, len(HEADERS) + 1):
        cell = ws.cell(1, col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="center")

    for row in ROWS:
        ws.append(row)
        r = ws.max_row
        fill = PAGE_FILLS.get(row[0])
        for col in range(1, len(HEADERS) + 1):
            cell = ws.cell(r, col)
            cell.alignment = wrap
            cell.border = thin
            if fill and col == 1:
                cell.fill = fill

    widths = [28, 42, 10, 48, 55, 70]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[1].height = 30
    for r in range(2, ws.max_row + 1):
        ws.row_dimensions[r].height = 95
    ws.auto_filter.ref = f"A1:F{ws.max_row}"
    ws.freeze_panes = "A2"

    notes = wb.create_sheet("Notes")
    notes["A1"] = "Field"
    notes["B1"] = "Value"
    notes["A1"].font = Font(bold=True)
    notes["B1"].font = Font(bold=True)
    note_rows = [
        ("Replace <TOKEN>", "Use a valid session_id from login"),
        ("Replace host", "Example hosts: http://192.168.0.122:9000 or http://10.100.100.43:9000"),
        ("Replace tenant", "Example tenant_id: c"),
        ("Auth headers", "username + session_id (panel session auth)"),
        ("Profile page route", "#/tenants/{id}/profile — brand & contact"),
        ("Profile menu route", "#/tenants/{id}/profile-menu — hours & notifications"),
        ("WhatsApp menu route", "#/tenants/{id}/menu — published Bot menu (read-only)"),
        ("Menu editor route", "#/tenants/{id}/menu-edit — edit options then Save & publish"),
        ("Website crawler / Files", "#/tenants/{id}/website-crawler — Preview / Download / Delete on file rows"),
        (
            "Example filename",
            "Automobile-WhatsApp-Assistant-Company-Document.pdf (use the exact name from the UI file list)",
        ),
        (
            "Scrubbed fields",
            "vocabulary, guardrails, notifications.brochure_url removed from detail/resolved/profile console payloads",
        ),
        (
            "Local-only actions",
            "Add option, Edit, Delete, Active/Inactive do not call an API until Save & publish",
        ),
    ]
    for i, (a, b) in enumerate(note_rows, 2):
        notes[f"A{i}"] = a
        notes[f"B{i}"] = b
        notes[f"B{i}"].alignment = wrap
    notes.column_dimensions["A"].width = 28
    notes.column_dimensions["B"].width = 90

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    try:
        wb.save(OUT)
        print(OUT)
    except PermissionError:
        wb.save(OUT_ALT)
        print(f"Original file locked; wrote {OUT_ALT}")


if __name__ == "__main__":
    main()
