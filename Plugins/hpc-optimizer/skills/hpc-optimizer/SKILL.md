---
name: hpc-optimizer
description: 驱动试验环。根据账本决定 baseline、keep、redirect、switch 或 stop，并提交作业、调用门控、写入账本。不定义应用的参数轴、算例、版本和接受标准。
---

# HPC Optimizer

共享环只做五步：读应用模板、搜索、提交作业、门控、把结果写入账本。不指定应用就不会启动。本版试验全部串行。本版不调用已有 skill。

```bash
python3 -m hpc_optimizer --app lammps --run-dir runs/lammps
```

## 场景

- 用户：鲲鹏上的 HPC 性能工程师。
- 前置条件：`skills/<应用>/` 里已经写好模板、门控规则、作业脚本和失败去向。
- 输入：该应用目录。不是任意源码树，也不是 profiling 报告。
- 输出：`ledger.json`，`version` 为 1。每条试验带架构。只有 aarch64、门控通过、且 `init.sh` 成功的试验是鲲鹏结果。
- 不适用：向量化改写、算子融合、NUMA、BIOS。这些不在本插件实现。
- 成功指标由应用模板声明。插件本身的验收是：不指定应用就失败；账本版本为 1，且每条试验都有 `arch` 和 `kunpeng`；`route` 为空时试验没有 `skill`。

## 契约

- HPCRunner 只为 aarch64 提供工具链版本（`init.sh` 里的 HPCKit 变量）。它不负责搜索。
- 试验状态只在账本里。不要把历史日志塞回对话。
- 搜索不读日志。快慢和数值是否有效只由门控写入账本。
- 失败交给哪个 skill，由应用目录的 `route` 声明。LAMMPS 的 `route` 为空。没有缺陷列表和检测器时，不路由到 `code-optimizer` 或 `app-tuner`。



## 能力边界

本技能决定下一次试验，不定义某个应用的物理空间。

- 做：读取 `--app` 的模板；用账本算出 `baseline`、`keep`、`redirect`、`switch`、`stop`；提交作业；调用门控；把结果写入账本。
- 交给应用技能：轴和取值、算例、`min_gain`、`budget`、门控正则和阈值、版本配方、工具链、`job.fmt`。
- 不做：不改应用源码，不做向量化、融合、NUMA、BIOS，不启动 ScienceFlow 进程。
- x86 上的热点、top-down 和访存采集不进 LAMMPS 的 `route`。应用分析改走 app-tuner 里的 `vtune-analysis`。aarch64 仍走 `kptools-devkit` 和 `arm-spe-analysis`。
- MPI 秩和 OpenMP 线程的配比走 app-tuner 的 `openmp-mpi-tuning`。作业把 `execution.threads` 导出为 `OMP_NUM_THREADS`。本技能不调用该技能，也不把它写入 `route`。

ScienceFlow 在这里只留下三条可执行规则：试验状态在账本里，中断后重复同一条命令即续跑；`decide` 不读日志；门控单独写入 `passed`、`kind`、`metric`。`keep`、`redirect`、`switch` 由这些字段计算，不是模型判断。并行试验和节点时间租约不在本版。

## 提示词入口

一次提示词只进一扇门。门由点名的对象决定，不由「优化这个应用」这几个字决定。三条门同时出现时，本技能只做第 1 扇。

1. 物理学配置。用户在 `skills/<应用>/` 定义应用：`<应用>.json` 的 `axes` 是要迭代的配置，`versions/<版本>/<架构>.json` 是该版本的配方，算例文件里的 `{轴名}` 对上这些轴。提示词只带 `/hpc-optimizer`，并用 `--app <应用>` 指定目录。ScienceFlow 在这里就是账本上的 `keep`、`redirect`、`switch`、`stop`。
2. 热点代码。对象是函数名和源码行。提示词带 `/kpbot-code-optimizer`，并写出函数和文件。本技能不调用它，也不把改过的源码放上搜索轴。
3. 采样调优。对象是进程数、线程数、编译选项、数学库或 FFT、绑核、BIOS。提示词带 `/kpbot-app-tuner`，或直接点名 `vtune-analysis`、`openmp-mpi-tuning`、`performance-library-selection-x86`、`compiler-optimization`、`cpu-affinity-optimization`。结论由用户写进版本配方或 `execution`，再单独用第 1 扇门测量。



## 和 hpc-lammps 配合

用户先在 `skills/lammps/` 写好搜索空间和接受标准，再重复执行本技能的命令。每执行一次只前进一步。对话里只看账本的 `action`、`metric`、`passed`、`kind`，不把 `job.log` 贴回来。