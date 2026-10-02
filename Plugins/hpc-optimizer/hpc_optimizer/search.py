def decide(template, trials):
    if len(trials) >= template["budget"]:
        return _stop("budget")
    if not trials:
        axis = template["axes"][0]
        return _go("baseline", axis["name"], axis["values"][0], template["execution"])
    last = trials[-1]
    if last["action"] == "stop":
        return _stop(last.get("reason") or "stopped")
    if last.get("skill") and not last.get("rerun"):
        return _go("keep", last["axis"], last["value"], last["execution"], rerun=True)
    if not last["passed"]:
        if last.get("kind") == "numeric":
            nxt = _advance(template, trials)
            if nxt is not None:
                return nxt
        return _stop("invalid")
    nxt = _advance(template, trials)
    if nxt is not None:
        return nxt
    if last["execution"]["mode"] == template["execution"]["mode"] and template.get("alt_execution"):
        axis = template["axes"][0]
        return _go("switch", axis["name"], axis["values"][0], template["alt_execution"])
    return _stop("exhausted")


def _advance(template, trials):
    last = trials[-1]
    axes = template["axes"]
    index = next(i for i, axis in enumerate(axes) if axis["name"] == last["axis"])
    values = axes[index]["values"]
    pos = values.index(last["value"])
    prev = _prev_metric(trials)
    gained = prev is not None and last["metric"] >= prev * (1 + template["min_gain"])
    if (prev is None or gained) and pos + 1 < len(values):
        return _go("keep", last["axis"], values[pos + 1], last["execution"])
    if index + 1 < len(axes):
        nxt = axes[index + 1]
        return _go("redirect", nxt["name"], nxt["values"][0], last["execution"])
    return None


def _prev_metric(trials):
    last = trials[-1]
    mode = last["execution"]["mode"]
    for trial in reversed(trials[:-1]):
        if (
            trial["axis"] == last["axis"]
            and trial["passed"]
            and trial["execution"]["mode"] == mode
            and trial["metric"] is not None
        ):
            return trial["metric"]
    return None


def _go(action, axis, value, execution, rerun=False):
    return {
        "action": action,
        "axis": axis,
        "value": value,
        "execution": dict(execution),
        "rerun": rerun,
        "reason": None,
    }


def _stop(reason):
    return {
        "action": "stop",
        "axis": None,
        "value": None,
        "execution": None,
        "rerun": False,
        "reason": reason,
    }
