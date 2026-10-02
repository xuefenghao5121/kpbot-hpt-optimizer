import re
from pathlib import Path


def judge(log_path, template):
    gate = template["gate"]
    text = Path(log_path).read_text(errors="replace")
    metric = _metric(text, gate["metric_pattern"])
    if metric is None or re.search(gate["compile_pattern"], text, re.I):
        return {"passed": False, "kind": "compile_fail", "metric": metric}
    drift = _drift(text, int(gate["drift_columns"]))
    if drift is None or drift > gate["drift_max"]:
        return {"passed": False, "kind": "numeric", "metric": metric}
    return {"passed": True, "kind": "ok", "metric": metric}


def _metric(text, pattern):
    found = re.findall(pattern, text)
    if not found:
        return None
    last = found[-1]
    if isinstance(last, tuple):
        value = float(last[0])
        unit = last[1].lower()
        if unit.startswith("k"):
            value /= 1000.0
        return value
    return float(last)


def _drift(text, columns):
    values = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != columns or not all(_num(part) for part in parts):
            continue
        values.append(float(parts[-1]))
    if len(values) < 2:
        return None
    base = abs(values[0]) or 1e-12
    return abs(values[-1] - values[0]) / base


def _num(token):
    try:
        float(token)
    except ValueError:
        return False
    return True
