---
name: hpc-lammps
description: 定义 LAMMPS 的参数轴、算例、版本配方和接受标准（能量漂移、Matom-step/s）。不决定下一次试验；那由 hpc-optimizer 根据账本计算。
---

# LAMMPS

用户是鲲鹏上的 HPC 性能工程师。前置条件是本目录里的配方和 `lammps.in`。输入是这些文件，不是一份任意源码或 profiling。一次试验改一个参数。本版试验全部串行。`min_gain` 为 `0.01`，是本算例选定的常数：同一条轴上至少再快 1% 才取下一个值。能量漂移不超过 `0.05`，也是本算例选定的常数，表示这 100 步里势能相对变化不得超过 5%。`balance` 大于等于 1 时，在 `run` 之前插入配方 `append` 里的 `balance 1.0 shift xyz 5 1.1`。只有账本里 `kunpeng` 为真的试验可以作为鲲鹏结果：架构是 aarch64、门控通过、并且日志里有 `HPC_OPT_INIT_OK`。

不适用：向量化改写、算子融合、绑核、BIOS。工具链失败和数值门失败留在本应用里，数值门失败会换轴。`route` 为空，不把 case 交给 `code-optimizer` 或 `app-tuner`。

```bash
python3 -m hpc_optimizer --app lammps --run-dir runs/lammps
```

在插件目录 `KPBot/Plugins/hpc-optimizer` 下执行。`HPC_OPT_ARCH` 选择工具链，缺省是本机架构。`HPC_OPT_VERSION` 选择 `versions/<版本>/<架构>.json`；不设时，若 `opt/*/src` 里恰好有一个已知源码包就用它，否则用 `lammps.json` 里该架构的默认版本。版本不是搜索轴。`HPC_OPT_RUN=1` 才执行。`HPC_OPT_JARVIS_ROOT` 只给 aarch64 的 HPCKit 版本变量使用。源码放在 `--run-dir/opt/lammps/src/`，文件名是配方里的 `source` 加上 `.tar.gz` 或 `.zip`，也可以是已经解出的源码目录。

## 能力边界

目录名是 `lammps`，卡片名是 `hpc-lammps`。本技能定义这一次 LAMMPS 搜索的空间和接受标准。下一次是 `keep`、`redirect`、`switch` 还是 `stop`，由 `hpc-optimizer` 读账本计算。

用户改本目录，不改 `hpc_optimizer/*.py`：

- `lammps.json`：轴和取值、`min_gain`、`budget`、`gate`、`execution`、`alt_execution`。`execution.threads` 由作业导出为 `OMP_NUM_THREADS`。秩和线程怎么配，用 app-tuner 的 `openmp-mpi-tuning`，不写进 `route`
- `lammps.in`：固定算例
- `versions/<版本>/<架构>.json`：该版本的源码包、编译器、启动器
- `job.fmt`：怎么解开源码包并编译运行

一次试验只改一个轴上的一个值。版本不是轴。编译失败和能量漂移留在本应用，`route` 为空。

## 按 ScienceFlow 的方法调 LAMMPS

1. 在本目录确认或修改版本、算例、轴和门控。空间或接受标准不对，就改这些文件。
2. 重复执行 `HPC_OPT_RUN=1 python3 -m hpc_optimizer --app lammps --run-dir runs/lammps`。状态在 `runs/lammps/ledger.json`。中断后执行同一条命令即续跑。
3. 只看账本决定你要不要继续执行命令：
   - `keep`：同一条轴还值得往下取一档。继续执行。
   - `redirect`：这一档收益不够，或数值门没过，环已经换轴。继续执行。
   - `switch`：参数轴走完且本条通过，环改用另一套 MPI 秩和线程数。继续执行。
   - `stop`，`reason` 为 `invalid`：编译失败，或数值门失败且没有下一档。改配方或算例后再决定是否清空账本重跑。
   - `stop`，`reason` 为 `exhausted` 或 `budget`：当前搜索空间走完。要再搜就改轴或 `budget`。
