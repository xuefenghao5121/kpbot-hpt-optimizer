import json
import os
import platform
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def load(path):
    path = Path(path)
    data = json.loads(path.read_text())
    data["_dir"] = str(path.parent)
    return data


def load_app(name):
    path = SKILLS / name / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"unknown app {name}")
    return load(path)


def host_arch():
    name = os.environ.get("HPC_OPT_ARCH") or platform.machine()
    if name in ("aarch64", "arm64"):
        return "aarch64"
    if name in ("x86_64", "amd64"):
        return "x86_64"
    raise ValueError(f"unsupported arch {name}")


def resolve(template, arch=None, run_dir=None):
    arch = arch or host_arch()
    try:
        target = dict(template["targets"][arch])
    except KeyError:
        raise ValueError(f"template has no target for {arch}") from None
    target["_dir"] = template.get("_dir", "")
    target["_job"] = template.get("job", "")
    pinned = os.environ.get("HPC_OPT_VERSION")
    local = None if pinned else _local_version(target["_dir"], arch, run_dir)
    version = pinned or local or target.get("version")
    if version and (Path(target["_dir"]) / "versions").is_dir():
        recipe = Path(target["_dir"]) / "versions" / version / f"{arch}.json"
        if not recipe.is_file():
            raise ValueError(f"no recipe for {arch} {version}")
        target["version"] = version
        target["recipe"] = f"versions/{version}/{arch}.json"
    return arch, target


def _local_version(app_dir, arch, run_dir):
    """Pick a version when exactly one known source is already under opt/*/src.

    ponytail: directory listing only, no archive introspection. Several matches
    stay on the pinned version; set HPC_OPT_VERSION to choose.
    """
    root = Path(app_dir) / "versions" if app_dir else None
    if not run_dir or not root or not root.is_dir():
        return None
    names = [p.name for src in Path(run_dir).glob("opt/*/src") if src.is_dir() for p in src.iterdir()]
    hits = []
    for ver in root.iterdir():
        recipe = ver / f"{arch}.json"
        if not recipe.is_file():
            continue
        source = json.loads(recipe.read_text()).get("source") or ""
        if source and any(n == source or n.startswith(source + ".") for n in names):
            hits.append(ver.name)
    return hits[0] if len(hits) == 1 else None
