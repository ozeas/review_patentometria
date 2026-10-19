from django import template

from core.records import SOURCE_LABELS

register = template.Library()


@register.filter
def get(d, k):
    try:
        return d.get(k) if hasattr(d, "get") else d[k]
    except (KeyError, IndexError, TypeError):
        return None


@register.filter
def pct1(v):
    """Vírgula decimal, uma casa: 67.6 → '67,6'."""
    try:
        return f"{float(v):.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return v


@register.filter
def join_list(v, sep="; "):
    if isinstance(v, (list, tuple, set)):
        return sep.join(str(x) for x in v)
    return v or ""


@register.filter
def source_label(s):
    return SOURCE_LABELS.get(s, s or "—")


@register.filter
def source_short(s):
    return {"lens": "L", "espacenet": "E", "google": "G", "derwent": "D"}.get(s, "?")
