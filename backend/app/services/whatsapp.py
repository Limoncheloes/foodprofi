from urllib.parse import quote

from app.config import settings


def build_order_text(order_id: str, order_date: str, restaurant_name: str, items: list[dict]) -> str:
    """Build the WhatsApp message text for a submitted procurement order.

    items: list of {"name": str, "quantity": float, "unit": str, "is_catalog_item": bool}
    """
    lines = [
        f"Заявка №{order_id[:8]} от {order_date}",
        f"Ресторан: {restaurant_name}",
        "",
    ]
    for i, item in enumerate(items, 1):
        label = "" if item["is_catalog_item"] else " (некаталог)"
        lines.append(f"{i}. {item['name']}{label} — {item['quantity']:.3f} {item['unit']}")
    lines.append("")
    lines.append("Статус: отправлено")
    return "\n".join(lines)


def build_whatsapp_urls(text: str) -> dict:
    """Return primary (group JID deep link) and fallback (wa.me) URLs.

    primary is None if WHATSAPP_GROUP_JID is not configured.
    """
    encoded = quote(text, safe="")
    fallback_phone = settings.whatsapp_curator_phone.lstrip("+")
    fallback = f"https://wa.me/{fallback_phone}?text={encoded}"

    primary = None
    if settings.whatsapp_group_jid:
        primary = f"whatsapp://send?groupid={settings.whatsapp_group_jid}&text={encoded}"

    return {"primary": primary, "fallback": fallback}
