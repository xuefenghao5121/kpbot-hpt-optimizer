import json
from pathlib import Path

VERSION = 1


def load(path):
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if data.get("version") != VERSION:
        raise ValueError(f"unsupported ledger version {data.get('version')}")
    return data["trials"]


def save(path, trials):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"version": VERSION, "trials": trials}
    path.write_text(json.dumps(body, indent=2) + "\n")
