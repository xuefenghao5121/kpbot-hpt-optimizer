---
name: openmp-mpi-tuning
description: >
  为 HPC 应用选择 MPI 进程数和 OpenMP 线程数的配比。当用户要调
  OMP_NUM_THREADS、ranks×threads、hybrid MPI+OpenMP，或 hpc-optimizer
  的 execution.threads / alt_execution 时触发。不改热点函数，不加
  pragma omp parallel for。
compatibility: aarch64, x86_64
---

# MPI 与 OpenMP 配比

本技能只给出秩和线程的配对、环境变量和验证命令。不改源码，不安装库，不写 hpc-optimizer 的 `route`。共享环不调用本技能。

推理场景里防止线程过提交仍走 `application-config-optimization`。绑核和 NUMA 仍走 `cpu-affinity-optimization`。

## 何时用

进程是 MPI，热点循环写共享数组（LAMMPS 的 `f[i]` 与 `f[j]` 就是这种），并且二进制带有应用自己的 OpenMP 包。只导出 `OMP_NUM_THREADS`、而二进制没有 OpenMP 包时，配比不生效。

LAMMPS 要同时满足：编译打开 `PKG_OPENMP`，输入在 `read_data` 之前有 `package omp N`，pair 使用 `/omp` 后缀。标量 `PairLJCutCoulLong::compute` 不读这个环境变量。不要在它的邻居循环上加 `#pragma omp parallel for`。

## 步骤

1. 读 `lscpu`：逻辑核、物理核。混合核机器只用已经测过不拖后腿的核，例如本机 P 核逻辑线程是 16，不要把 E 核算进乘积。
2. 确认二进制和输入真的走 OpenMP 包。否则本技能的结论是 `not_applicable`，先换包再配比。
3. 配对满足 `ranks * threads` 不超过第 1 步的可用核数，`threads >= 1`。一次只改秩或只改线程。纯 MPI（`threads = 1`）保留为对照。
4. 启动时导出 `OMP_NUM_THREADS=<threads>`，MPI 用 `-np <ranks>`。hpc-optimizer 的作业从 `execution.threads` 写这个变量。配比写在应用模板的 `execution` 或 `alt_execution`，不写进 `route`。
5. 用应用自己的门控比较。LAMMPS 沿用 `min_gain` 0.01 和能量漂移 0.05：快过 1% 且能量通过才保留该配对。

## 输出

```json
{
  "status": "recommended",
  "usable_cores": 16,
  "openmp_package": true,
  "pairs": [{"ranks": 16, "threads": 1}, {"ranks": 8, "threads": 2}],
  "env": ["OMP_NUM_THREADS"],
  "verification_status": "not_verified"
}
```

`openmp_package` 为假时 `status` 写 `not_applicable`，`pairs` 为空。
