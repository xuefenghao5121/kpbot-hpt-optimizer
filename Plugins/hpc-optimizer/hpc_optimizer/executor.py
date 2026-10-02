import hashlib
import json
import os
import subprocess
from pathlib import Path


def build_stamp(recipe):
    """Identity of the binary. A new stamp rebuilds; runtime fields do not."""
    parts = [
        recipe.get("version", ""),
        recipe.get("source", ""),
        recipe.get("packages", ""),
        recipe.get("cxx_flags", ""),
        recipe.get("cxx_compiler", ""),
        recipe.get("fft", ""),
        "\n".join(recipe.get("cmake") or []),
    ]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


class JarvisExecutor:
    """aarch64：把试验交给 HPCRunner。不读日志。"""

    def __init__(self, jarvis_root, run=False):
        self.jarvis_root = Path(jarvis_root)
        self.run = run

    def commands(self, spec):
        config = self.jarvis_root / spec["target"]["jarvis_config"]
        root = self.jarvis_root
        return [
            f"cd {root}",
            f"./jarvis -use {config}",
            "./jarvis -b",
            "./jarvis -r",
        ]

    def submit(self, spec, work):
        return _run(self.commands(spec), work, self.run)


class NativeExecutor:
    """按应用目录里的作业模板提交。不读日志。"""

    def __init__(self, recipe, case, script, run=False, jarvis_root=None):
        self.recipe = recipe
        self.case = case
        self.script = script
        self.run = run
        self.jarvis_root = jarvis_root

    def commands(self, spec):
        recipe = self.recipe
        setup = (
            'cd "$JARVIS_ROOT"\nsource ./init.sh\necho HPC_OPT_INIT_OK'
            if self.jarvis_root
            else ""
        )
        env = "\n".join(recipe.get("env") or [])
        deps = ""
        if recipe.get("dependency"):
            tools = " ".join(recipe["dependency"])
            deps = f'for tool in {tools}; do command -v "$tool"; done'
        fft_line = f"    -DFFT={recipe['fft']} \\\n" if recipe.get("fft") else ""
        cmake_extra = "".join(f"    {arg} \\\n" for arg in recipe.get("cmake") or [])
        text = self.script.format(
            build_id=build_stamp(recipe),
            setup=setup,
            env=env,
            deps=deps,
            ranks=spec["execution"]["ranks"],
            threads=spec["execution"]["threads"],
            fft_line=fft_line,
            cmake_extra=cmake_extra,
            cxx=recipe.get("cxx_compiler", "mpicxx"),
            launcher=recipe.get("launcher", "mpirun"),
            **{key: recipe[key] for key in ("binary", "source", "download_url", "packages", "cxx_flags", "version")},
        )
        return [line for line in text.splitlines() if line.strip()]

    def submit(self, spec, work):
        work = Path(work).resolve()
        work.mkdir(parents=True, exist_ok=True)
        (work / "in.trial").write_text(self.input_text(spec))
        # ponytail: only data.spce; a template file list if a case needs more inputs
        data = Path((spec.get("target") or {}).get("_dir") or "") / "data.spce"
        if data.is_file():
            (work / "data.spce").write_bytes(data.read_bytes())
        if self.jarvis_root:
            header = [
                "#!/bin/bash",
                f'JARVIS_ROOT="{Path(self.jarvis_root).resolve()}"',
                f'PREFIX="{self.recipe["prefix"]}"',
            ]
        else:
            prefix = (work.parent.parent / "opt" / self.recipe.get("install_name", "app")).resolve()
            header = ["#!/bin/bash", f'PREFIX="{prefix}"']
        header.append(f'SRC="$PREFIX/src"')
        header.append(f'WORK="{work}"')
        script = work / "job.sh"
        script.write_text("\n".join(header + self.commands(spec)) + "\n")
        script.chmod(0o755)
        log = work / "job.log"
        if self.run:
            with log.open("w") as out:
                subprocess.run(["bash", str(script)], stdout=out, stderr=subprocess.STDOUT, check=False)
        elif not log.exists():
            log.write_text("")
        return log

    def input_text(self, spec):
        params = dict(self.recipe["defaults"])
        params.update(spec.get("params") or {})
        text = self.case.format(**params)
        extra = [
            rule["line"]
            for rule in self.recipe.get("append") or []
            if float(params.get(rule["param"], 0)) >= float(rule["min"])
        ]
        if not extra:
            return text
        lines = text.splitlines()
        # ponytail: a command after `run` is outside the timed section
        idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith("run ")), None)
        if idx is None:
            lines.extend(extra)
        else:
            lines[idx:idx] = extra
        return "\n".join(lines) + "\n"


def make(target, run=False, jarvis_root=None):
    if target.get("backend") == "jarvis":
        return JarvisExecutor(jarvis_root or default_root(), run=run)
    if target.get("backend") == "native":
        app_dir = Path(target["_dir"])
        recipe_path = app_dir / target["recipe"]
        if not recipe_path.is_file():
            raise ValueError(f"no recipe {target['recipe']}")
        recipe = json.loads(recipe_path.read_text())
        case = (app_dir / target["case"]).read_text()
        script = (app_dir / target["_job"]).read_text()
        root = default_root() if recipe.get("use_jarvis_root") else None
        return NativeExecutor(recipe, case, script, run=run, jarvis_root=root)
    raise ValueError(f"unknown backend {target.get('backend')}")


def _run(commands, work, run):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    script = work / "job.sh"
    script.write_text("#!/bin/bash\nset -e\n" + "\n".join(commands) + "\n")
    script.chmod(0o755)
    log = work / "job.log"
    if run:
        with log.open("w") as out:
            subprocess.run(["bash", str(script)], stdout=out, stderr=subprocess.STDOUT, check=False)
    elif not log.exists():
        log.write_text("")
    return log


def default_root():
    env = os.environ.get("HPC_OPT_JARVIS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4] / "hpcrunner"
