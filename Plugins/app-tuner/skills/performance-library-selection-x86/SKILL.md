---
name: performance-library-selection-x86
description: >
  在 x86_64 上按热点占比选择可替换的性能库。数学、BLAS、稀疏矩阵和 FFT
  优先 Intel oneMKL。当用户要把 ARM 的 performance-library-selection 换到
  x86、或要把 KISS/FFTW/OpenBLAS/libm 换成 oneMKL、oneDNN、ISA-L 时触发。
  aarch64 不使用本技能。
compatibility: x86_64
---

# x86 性能库选型

aarch64 的库表在 `kpbot-app-tuner/subskills/performance-library-selection/`。本技能只换候选库和接入方式，步骤、阈值和输出字段与那份相同。

`uname -m` 不是 `x86_64` 时停止。不要推荐 KML、毕昇 stringlib、vectorBLAS、`ascend_runtime`。

本技能只出推荐和验证命令，不安装库，不改二进制，不做 `LD_PRELOAD`。

## 步骤

1. 采环境指纹：`uname -srm`、`lscpu` 的型号、`nproc`。有目标进程时读 `/proc/<pid>/maps` 里的 `.so`。热点用已有 perf 或 VTune 报告；没有报告就记 `perf 采样=未尝试`，置信度最高 `experience_only`。
2. 按下面的正则把热点符号归到类别，各类单独加总。占比 ≥ 0.5% 才进入推荐。
3. 输出和 ARM 技能相同的三块：`all_library_verification_results[]`（`verification_status=not_verified`）、`candidate_actions[]`、体检报告。报告里的 CPU 架构写 `x86_64`。

符号归类与 ARM 技能相同：`malloc|free|je_malloc|tc_malloc`、`memcpy|memset`、`gemv|gemm|cblas`、`spmv|spgemm`、`sin|cos|exp|log|vml|svml`、`fft|ifft|dft`、`conv|relu|dnn`，以及压缩、加密、JSON、正则、视频、protobuf、SQL、KTLS、RocksDB。

| 占比 | confidence | 主框架验证次数 |
|---|---|---|
| > 5% | high | ≥3 |
| 2–5% | medium | ≥2 |
| 0.5–2% | low | ≥1 |
| < 0.5% | — | 跳过该类 |
| 没有热点报告 | experience_only | 可选 |

热点符号落在应用自己的二进制里、而不是 `libm`、`libfftw`、`libblas`、`libopenblas` 或 `libmkl` 时，math、fft、linear_algebra 记 `not_recommended`。内联的 `exp` 换不成 oneMKL VML。

## x86 候选库

| 类别 | 当前常见库 | x86 候选 | 接入 |
|---|---|---|---|
| allocators | glibc malloc | jemalloc，线程多时 tcmalloc | `LD_PRELOAD`。进程已经链了 jemalloc 或 tcmalloc 则 `not_recommended` |
| memory_operations | glibc | 保持 glibc。glibc 在 x86 上已按 AVX2/AVX-512 选 mem* | 不换毕昇 stringlib |
| math | libm / libmvec | oneMKL VML | 编译期 `-lmkl_rt`，或让调用走 VML。不是 `LD_PRELOAD` |
| fft | KISS、FFTW | oneMKL DFT | 编译期。LAMMPS 为 `-DFFT=MKL` 并设置 MKL 头文件和库 |
| linear_algebra | libblas、OpenBLAS | oneMKL BLAS | 编译期 `-lmkl_rt`。已链 MKL 则 `not_recommended` |
| sparse_linear_algebra | 参考实现 | oneMKL Sparse BLAS | 编译期 |
| dnn | 框架自带算子 | oneDNN | 编译期或运行时加载 oneDNN |
| compression | zlib | ISA-L，或保持 zlib | ISA-L 只在压缩或 CRC 符号达到阈值时推荐 |
| crypto | OpenSSL | OpenSSL（AES-NI） | 已链 OpenSSL 则不换 |
| hash_functions | 自带 CRC | ISA-L CRC、xxHash | 同 ARM 技能的阈值 |
| json | RapidJSON | sonic-cpp、RapidJSON | 同 ARM |
| pattern_matching | PCRE | Hyperscan | x86 是 Hyperscan 的原生平台 |
| video / serialization / sql_acceleration / network / kv_storage | 同 ARM 技能 | X264/X265、Protobuf、sparksql_native、KTLS、RocksDB | 同 ARM，只在对应符号达到阈值时推荐 |

oneMKL 三块（VML、DFT、BLAS）互相独立。只推荐热点类别命中的那一块。安装检查只读：`ldconfig -p | grep libmkl` 或 `/opt/intel/oneapi/mkl`。找不到库时 `installation_feasibility=not_feasible`，`recommendation=inconclusive`，不在本技能里安装。

## 验证命令

分配器：

```bash
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2 <command>
grep jemalloc /proc/<pid>/maps
```

回退是去掉 `LD_PRELOAD`。

oneMKL 必须重链或重编。回退是改回原来的 FFT 和 BLAS 选项并重新安装旧二进制。不要用 `LD_PRELOAD=libmkl_rt.so` 代替编译期链接。

## 结果字段

与 ARM 技能的未验证模板一致：`library_name`、`verification_status=not_verified`、`confidence`、`recommendation`、`reason`、`evidence_sources`。推荐项再写一条 `candidate_actions`：`action_id`、`title`、`category`、`change_mode`（`ld_preload` 或 `rebuild`）、`implementation_plan`、`validation_plan`、`rollback`。
