import os
from pathlib import Path

from hpc_optimizer.executor import make
from hpc_optimizer.gate import judge
from hpc_optimizer.ledger import load as load_ledger
from hpc_optimizer.ledger import save
from hpc_optimizer.router import route
from hpc_optimizer.search import decide
from hpc_optimizer.template import load as load_template
from hpc_optimizer.template import load_app, resolve


def step(run_dir, template_path=None, executor=None, app=None):
    if template_path:
        template = load_template(template_path)
    elif app:
        template = load_app(app)
    else:
        raise ValueError("pass --app or --template")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    arch, target = resolve(template, run_dir=run_dir)
    path = run_dir / "ledger.json"
    trials = load_ledger(path)
    decision = decide(template, trials)
    if decision["action"] == "stop":
        skill = route(template, stop_reason=decision["reason"])
        if skill and trials and not trials[-1].get("skill"):
            trials[-1]["skill"] = skill
            save(path, trials)
        return decision
    work = run_dir / "trials" / str(len(trials))
    if executor is None:
        executor = make(target, run=os.environ.get("HPC_OPT_RUN") == "1")
    params = {axis["name"]: axis["values"][0] for axis in template["axes"]}
    params[decision["axis"]] = decision["value"]
    spec = {
        "target": target,
        "axis": decision["axis"],
        "value": decision["value"],
        "execution": decision["execution"],
        "params": params,
    }
    log_path = executor.submit(spec, work)
    verdict = judge(log_path, template)
    trial = {
        "axis": decision["axis"],
        "value": decision["value"],
        "execution": decision["execution"],
        "log": str(log_path),
        "metric": verdict["metric"],
        "passed": verdict["passed"],
        "kind": verdict["kind"],
        "action": decision["action"],
        "rerun": decision["rerun"],
        "arch": arch,
        "kunpeng": _kunpeng(arch, verdict["passed"], log_path),
    }
    if target.get("version"):
        trial["version"] = target["version"]
    skill = route(template, kind=verdict["kind"])
    if skill:
        trial["skill"] = skill
    trials.append(trial)
    save(path, trials)
    return trial


def _kunpeng(arch, passed, log_path):
    if arch != "aarch64" or not passed:
        return False
    text = Path(log_path).read_text(errors="replace")
    return "HPC_OPT_INIT_OK" in text


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--app", default=None)
    parser.add_argument("--template", default=None)
    args = parser.parse_args(argv)
    print(step(args.run_dir, args.template, app=args.app))


if __name__ == "__main__":
    main()
