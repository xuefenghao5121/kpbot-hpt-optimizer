def route(template, kind=None, stop_reason=None):
    table = template.get("route") or {}
    key = kind or stop_reason
    if not key:
        return None
    skill = table.get(key)
    return skill or None
