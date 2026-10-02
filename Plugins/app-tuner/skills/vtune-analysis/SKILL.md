---
name: vtune-analysis
description: >
  在 x86_64 上用 Intel VTune 采集热点、top-down 微架构和访存。当用户要在本机
  替代鲲鹏 DevKit 或 ARM SPE、做函数热点、火焰图、Microarchitecture Exploration、
  Memory Access、PEBS、Cache Miss、分支误预测，或说把应用分析路由到 VTune 时触发。
  aarch64 不使用本技能。
compatibility: x86_64, requires Intel VTune Profiler
---

# VTune 分析

x86 上的微架构采集走这里。鲲鹏 DevKit 和 ARM SPE 仍只在 aarch64 上用。`hpc-optimizer` 的 LAMMPS `route` 不调用本技能：那张表只给编译失败、数值门和停止原因记账。应用分析要采样时，直接跑下面的脚本。

硬件事件需要 root。本机 `perf_event_paranoid=4` 时，脚本会用 `sudo -n` 重新执行。不要把 root 密码写进对话。

## 安装与检查

```bash
bash scripts/install_vtune.sh
bash scripts/run_vtune.sh check
```

## 采集

必须带 `-duration`，单位秒。结果目录自定。

```bash
# 函数热点。对应 DevKit 的热点 / 火焰图
bash scripts/run_vtune.sh -collect hotspots -duration 15 -result-dir vtune-hotspots -- <command>

# top-down。对应 DevKit 的 top-down
bash scripts/run_vtune.sh -collect uarch-exploration -duration 15 -result-dir vtune-uarch -- <command>

# 访存、Cache、带宽。对应 ARM SPE 的 load/store 采样
bash scripts/run_vtune.sh -collect memory-access -duration 15 -result-dir vtune-memory -target-pid <pid>
```

正在跑的进程用 `-target-pid`，不要再在命令末尾加 `--`。

## 报告

```bash
bash scripts/run_vtune.sh -report hotspots -result-dir vtune-hotspots -format text
bash scripts/run_vtune.sh -report summary -result-dir vtune-uarch -format text
```

报告只摘录热点函数、top-down 占比和访存瓶颈。不要把 VTune 原始目录贴回对话。
