#!/usr/bin/env python3
"""One run of the LAMMPS loop: baseline, keep, redirect, switch, and skill routing."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hpc_optimizer.executor import JarvisExecutor, build_stamp, default_root, make
import hpc_optimizer.executor as executor_mod
from hpc_optimizer.ledger import load
from hpc_optimizer.loop import step
from hpc_optimizer.template import load_app, resolve

def log(metric, energies, extra=""):
    body = "\n".join(f"{i} 300 {e}" for i, e in enumerate(energies))
    return f"{extra}\nPerformance: 1 ns/day, 1 hours/ns, 1 timesteps/s, {metric} Matom-step/s\n{body}\n"


class Scripted:
    def __init__(self, texts):
        self.texts = list(texts)
        self.specs = []

    def submit(self, spec, work):
        self.specs.append(spec)
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        path = work / "job.log"
        path.write_text(self.texts.pop(0))
        return path


def template():
    return {
        "app": "lammps",
        "targets": {
            "x86_64": {
                "backend": "native",
                "toolchain": "gcc+openmpi",
                "recipe": "lammps.x86_64.json",
                "case": "lammps.in",
            },
            "aarch64": {
                "backend": "jarvis",
                "jarvis_config": "templates/lammps/2023.8.2/data.lammps.arm.cpu.config",
                "toolchain": "bisheng+hmpi+fftw",
            },
        },
        "execution": {"mode": "mpi", "nodes": 1, "ranks": 4, "threads": 1},
        "alt_execution": {"mode": "mpi+omp", "nodes": 1, "ranks": 2, "threads": 2},
        "min_gain": 0.01,
        "gate": {
            "metric_pattern": r"([\d.]+)\s+(katom|Matom)-step/s",
            "compile_pattern": r"error:|Error \d|command not found",
            "drift_columns": 3,
            "drift_max": 0.05,
        },
        "route": {},
        "budget": 8,
        "axes": [
            {"name": "timestep", "values": [0.001, 0.002]},
            {"name": "neighbor_skin", "values": [0.3]},
        ],
    }


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        path = tmp / "lammps.json"
        path.write_text(json.dumps(template()))
        run = tmp / "run"
        exe = Scripted([
            log(100, [-10.0, -10.01]),
            log(110, [-10.0, -10.01]),
            log(110, [-10.0, -10.01]),
            log(100, [-10.0, -12.0]),
            log(100, [-10.0, -10.01]),
        ])
        actions = [step(run, path, exe)["action"] for _ in range(3)]
        assert actions == ["baseline", "keep", "redirect"], actions
        failed = step(run, path, exe)
        assert failed["action"] == "switch" and failed["kind"] == "numeric" and "skill" not in failed, failed
        assert failed["kunpeng"] is False
        retry = step(run, path, exe)
        assert retry["action"] == "keep" and retry["rerun"] is False, retry
        import hpc_optimizer.search as search_mod
        assert "job.log" not in Path(search_mod.__file__).read_text()

    jarvis = default_root()
    arm = template()["targets"]["aarch64"]
    assert (jarvis / arm["jarvis_config"]).is_file(), jarvis
    cmds = "\n".join(JarvisExecutor(jarvis).commands({"target": arm}))
    assert "./jarvis -b" in cmds and "./jarvis -r" in cmds
    assert "data.lammps.arm.cpu.config" in cmds

    data = load_app("lammps")
    spec = {
        "axis": "timestep",
        "value": 0.002,
        "execution": {"mode": "mpi", "nodes": 1, "ranks": 4, "threads": 1},
        "params": {"timestep": 0.002, "neighbor_skin": 0.3, "cutoff": 2.5, "balance": 0},
    }
    _, arm_target = resolve(data, "aarch64")
    _, x86_target = resolve(data, "x86_64")
    arm = make(arm_target, run=False)
    arm_txt = "\n".join(arm.commands(spec))
    assert "hpckit" in arm_txt and "bisheng" in arm_txt and "hmpi" in arm_txt and "kml" in arm_txt
    assert "libfftw3.a" in arm_txt
    assert "-DFFT=KISS" not in arm_txt
    x86 = make(x86_target, run=False)
    x86_txt = "\n".join(x86.commands(spec))
    assert "hpckit" not in x86_txt and "kml" not in x86_txt
    assert "lammps-2Aug2023.tar.gz" in x86_txt
    assert "zipfile -e" in x86_txt and ".hpc-opt-version" in x86_txt
    assert "-newer" in x86_txt
    recipe = json.loads((Path(x86_target["_dir"]) / x86_target["recipe"]).read_text())
    assert build_stamp(recipe) in x86_txt
    assert build_stamp(dict(recipe, cxx_flags=recipe["cxx_flags"] + " -g")) != build_stamp(recipe)
    assert build_stamp(dict(recipe, packages=recipe["packages"] + " OPENMP")) != build_stamp(recipe)
    assert build_stamp(dict(recipe, source="other-tree")) != build_stamp(recipe)
    assert build_stamp(dict(recipe, fft="MKL")) != build_stamp(recipe)
    assert "ALL_PACKAGES KSPACE MANYBODY MOLECULE RIGID GRANULAR" in x86_txt
    assert "-DFFT=KISS" in x86_txt
    assert "lmp_mpi -in in.trial" in x86_txt
    assert "OMP_NUM_THREADS=1" in x86_txt
    threaded = dict(spec)
    threaded["execution"] = dict(spec["execution"], ranks=2, threads=2)
    assert "OMP_NUM_THREADS=2" in "\n".join(x86.commands(threaded))
    assert "timestep 0.002" in x86.input_text(spec)
    assert "balance 1.0" not in x86.input_text(spec)
    balanced = dict(spec)
    balanced["params"] = dict(spec["params"], balance=1)
    assert arm.input_text(spec) == x86.input_text(spec)
    balanced_text = x86.input_text(balanced)
    assert "balance 1.0 shift xyz 5 1.1" in balanced_text
    assert balanced_text.index("balance 1.0 shift xyz 5 1.1") < balanced_text.index("run 100")
    assert "balance 1.0" not in Path(executor_mod.__file__).read_text()
    import os
    os.environ["HPC_OPT_VERSION"] = "2025.7.22"
    try:
        _, picked = resolve(data, "x86_64")
        assert picked["version"] == "2025.7.22"
        newer = "\n".join(make(picked, run=False).commands(spec))
        assert "lammps-stable_22Jul2025" in newer and "lammps-2Aug2023" not in newer
    finally:
        os.environ.pop("HPC_OPT_VERSION", None)
    try:
        resolve(data, "aarch64")
        os.environ["HPC_OPT_VERSION"] = "2025.7.22"
        resolve(data, "aarch64")
    except ValueError as exc:
        assert "no recipe for aarch64 2025.7.22" in str(exc), exc
    else:
        raise SystemExit("missing arch recipe must fail")
    finally:
        os.environ.pop("HPC_OPT_VERSION", None)
    with tempfile.TemporaryDirectory() as src_root:
        src = Path(src_root) / "opt" / "lammps" / "src"
        src.mkdir(parents=True)
        (src / "lammps-stable_22Jul2025.zip").write_text("")
        _, local = resolve(data, "x86_64", src_root)
        assert local["version"] == "2025.7.22", local["version"]
        (src / "lammps-2Aug2023.tar.gz").write_text("")
        _, ambiguous = resolve(data, "x86_64", src_root)
        assert ambiguous["version"] == "2023.8.2", ambiguous["version"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        path = tmp / "lammps.json"
        data = template()
        data.pop("alt_execution")
        data["axes"] = [{"name": "timestep", "values": [0.001]}]
        path.write_text(json.dumps(data))
        run = tmp / "run"
        exe = Scripted([log(100, [-10.0, -10.01])])
        step(run, path, exe)
        done = step(run, path, exe)
        assert done["action"] == "stop" and done["reason"] == "exhausted", done
        assert "skill" not in load(run / "ledger.json")[-1]

    compile_log = "make: *** [all] Error 2\n"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        path = tmp / "lammps.json"
        path.write_text(json.dumps(template()))
        run = tmp / "run"
        trial = step(run, path, Scripted([compile_log]))
        assert "skill" not in trial and trial["kind"] == "compile_fail" and trial["metric"] is None
        assert trial["arch"] in ("aarch64", "x86_64") and trial["kunpeng"] is False
        stopped = step(run, path, Scripted(["unused"]))
        assert stopped["action"] == "stop" and stopped["reason"] == "invalid", stopped
        empty = step(tmp / "dry", path, Scripted([""]))
        assert empty["kind"] == "compile_fail" and empty["passed"] is False
        dry_stop = step(tmp / "dry", path, Scripted(["unused"]))
        assert dry_stop["action"] == "stop" and dry_stop["reason"] == "invalid"
        raw = json.loads((run / "ledger.json").read_text())
        assert raw["version"] == 1 and isinstance(raw["trials"], list)
        assert all("arch" in row and "kunpeng" in row for row in raw["trials"])

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        path = tmp / "lammps.json"
        path.write_text(json.dumps(template()))
        run = tmp / "run"
        import os
        os.environ["HPC_OPT_ARCH"] = "aarch64"
        try:
            ready = log(100, [-10.0, -10.01], extra="HPC_OPT_INIT_OK")
            ok_trial = step(run, path, Scripted([ready]))
            assert ok_trial["passed"] and ok_trial["kunpeng"] is True
            bad = step(tmp / "fail", path, Scripted([log(100, [-10.0, -10.01])]))
            assert bad["passed"] and bad["kunpeng"] is False
        finally:
            os.environ.pop("HPC_OPT_ARCH", None)
    try:
        step(Path(tempfile.mkdtemp()))
    except ValueError:
        pass
    else:
        raise SystemExit("missing app must fail")
    try:
        step(Path(tempfile.mkdtemp()), app="no-such-app")
    except ValueError as exc:
        assert "unknown app" in str(exc), exc
    else:
        raise SystemExit("unknown app must fail")

    print("ok")


if __name__ == "__main__":
    main()
