from django import template

from core.records import SOURCE_LABELS

register = template.Library()


@register.filter
def get(d, k):
    try:
        if hasattr(d, "get"):
            valor = d.get(k)
            if valor is None and isinstance(k, int):
                valor = d.get(str(k))  # chaves viram texto ao passar por JSON
            return valor
        return d[k]
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
