# Results Format (CSV outputs)

This document specifies the **exact CSV schemas** produced by the Artifact Evaluation (AE) scripts.
All CSV outputs are written under:

- `ae/results/`

These CSVs are intended to be machine-readable and easy to compare against paper tables.

## 1. Output files overview

Main result files:

- `ae/results/table1.csv`
- `ae/results/table2a.csv`
- `ae/results/table2b.csv`
- `ae/results/table3_raw.csv`
- `ae/results/table3.csv`
- `ae/results/table4.csv`
- `ae/results/table5.csv`

### Logs (runtime/debug)

AE runs create a **timestamped log directory** per invocation of the table runner (e.g., `run_all_tables.sh`):

- `ae/results/logs/<YYYYMMDD-HHMMSS>/`

Within that directory:

- Runner logs (captured via shell `tee`), e.g.
  - `run_table1.log`, `run_table2a.log`, ..., `run_table5.log`
- Table 2 debug logs (only written when a run fails or misses a requested report iteration), e.g.
  - `table2a_qrw_n128.txt`
  - `table2a_qrw_n128_per_iter.log`
  - `table2b_grover_n16.txt`
  - `table2b_grover_n16_per_iter.log`
- Table 3 per-run failure logs:
  - `ae/results/logs/<timestamp>/table3/*.txt`

> Note: When running a single table script directly (without the AE runner), logs fall back to `ae/results/logs/` unless `AE_LOG_DIR` is set.

---

## 2. Table 1 (`ae/results/table1.csv`) — RUS while-loops (preset mode)

### 2.1 Header (exact)

```text
benchmark,qubits,gates_per_iteration,iterations,time_seconds
```

### 2.2 Column semantics

- `benchmark`: Benchmark identifier (e.g., a RUS instance name).
- `qubits`: Total number of qubits used by the circuit.
- `gates_per_iteration`: Number of quantum gate operations in one loop iteration (as counted by the runner).
- `iterations`: Number of loop iterations executed (forced by preset pattern in this benchmark).
- `time_seconds`: Total runtime for this benchmark configuration (seconds).

## 3. Table 2a (`ae/results/table2a.csv`) — QRW sequential circuits (BDDSeqSim)

### 3.1 Header (exact)

```text
benchmark,qubits,gates_per_iteration,iterations,time_seconds,status
```

### 3.2 Column semantics

- `benchmark`: Benchmark identifier (fixed to `QRW`).
- `qubits`: Total number of qubits.
- `gates_per_iteration`: Number of gates executed per iteration.
- `iterations`: Number of iterations executed.
- `time_seconds`: Total runtime for this configuration (seconds).
- `status`: Run status string. Typical values:

  - `success`
  - `timeout`
  - `error`
  - `success_missing_iter` / `timeout_missing_iter` / `error_missing_iter` (reported when a requested iteration is missing).

Logs for Table 2a:

- runner log: `ae/results/logs/<timestamp>/run_table2a.log`
- debug logs (only on failure/missing report): `ae/results/logs/<timestamp>/table2a_qrw_n*.txt`
- per-iteration logs (archived from `exp/simulation/data/qrw_<n>.log`): `ae/results/logs/<timestamp>/table2a_qrw_n*_per_iter.log`

## 4. Table 2b (`ae/results/table2b.csv`) — Grover sequential circuits (BDDSeqSim)

### 4.1 Header (exact)

```text
benchmark,qubits,gates_per_iteration,iterations,time_seconds,status
```

### 4.2 Column semantics

Same semantics as Table 2a.

Logs for Table 2b:

* runner log: `ae/results/logs/<timestamp>/run_table2b.log`
* debug logs (only on failure/missing report): `ae/results/logs/<timestamp>/table2b_grover_n*.txt`
* per-iteration logs (archived from `exp/simulation/data/grover_<n>.log`): `ae/results/logs/<timestamp>/table2b_grover_n*_per_iter.log`

## 5. Table 3 raw (`ae/results/table3_raw.csv`) — Random while-loops (sample mode), per-run log

### 5.1 Header (exact)

```text
benchmark,qubits,gates,mid_meas,run_id,rng_seed,status,time_seconds,note
```

### 5.2 Column semantics

- `benchmark`: Configuration identifier (e.g., `rqc_q100_g50_m5`).
- `qubits`: Total number of qubits.
- `gates`: Total gate count for the circuit instance.
- `mid_meas`: Number of mid-circuit measurements.
- `run_id`: Integer repeat index for this configuration (one row per run).
- `rng_seed`: Seed used for sampling in this run (if deterministic sampling is enabled by the runner). If deterministic sampling is disabled, this may still record a seed value used internally.
- `status`: Run status string. Typical values:
  - `SUCCESS`
  - `TIMEOUT`
  - `LOOPOUT`
  - `ERROR`
- `time_seconds`: Runtime of this single run (seconds).
- `note`: Optional extra info (error message, timeout reason, etc.).

For failures, the runner may also write a per-run log to:

- `ae/results/logs/<timestamp>/table3/` (one file per failing run)

## 6. Table 3 summary (`ae/results/table3.csv`) — Random while-loops (sample mode), aggregated statistics

### 6.1 Header (exact)

```text
benchmark,qubits,gates,mid_meas,valid_runs,median_seconds,q1_seconds,q3_seconds
```

### 6.2 Column semantics

- `benchmark`, `qubits`, `gates`, `mid_meas`: Same as Table 3 raw.
- `valid_runs`: Number of runs included in the statistics (rows in `table3_raw.csv` with `status == SUCCESS`).
- `median_seconds`: Median runtime over valid runs.
- `q1_seconds`: First quartile (0.25 quantile) runtime over valid runs.
- `q3_seconds`: Third quartile (0.75 quantile) runtime over valid runs.

Interpretation:

Sampling runtimes are often right-skewed; therefore, Table 3 uses median and IQR (Q1–Q3).

## 7. Table 4 (`ae/results/table4.csv`) — Quantum state reachability (QRW)

### 7.1 Header (exact)

```text
qubits,k,reachable,probability,time_seconds
```

### 7.2 Column semantics

- `qubits`: Total number of qubits in the experiment.
- `k`: Iteration count (e.g., after `k` iterations).
- `reachable`: Reachability indicator (`Yes` or `No`).
- `probability`: Binary64 reachability probability for the target event encoded
  by the preset measurement pattern. Branch/model-count evaluation is symbolic
  before the public float conversion.
- `time_seconds`: Runtime for this configuration (seconds).

## 8. Table 5 (`ae/results/table5.csv`) — Measurement-outcome reachability (RUS termination patterns)

### 8.1 Header (exact)

```text
k,ppath,pterm,time_seconds_avg,repeat_runs
```

### 8.2 Column semantics

- `k`: Pattern index / termination-attempt parameter (e.g., length of the failure-prefix).
- `ppath`: Probability of the exact termination pattern at index `k` (single-path probability).
- `pterm`: Cumulative termination probability up to index `k` (typically a prefix-sum over `ppath`).
- `time_seconds_avg`: Average runtime over repeats (seconds).
- `repeat_runs`: Number of repeats used for computing the average runtime.

## 9. Quick sanity-check commands

After running the smoke test:

```bash
./ae/scripts/run_smoke.sh
```

Verify headers:

```bash
head -n 1 ae/results/table1.csv
head -n 1 ae/results/table2a.csv
head -n 1 ae/results/table2b.csv
head -n 1 ae/results/table3_raw.csv
head -n 1 ae/results/table3.csv
head -n 1 ae/results/table4.csv
head -n 1 ae/results/table5.csv
```

If a CSV is missing or contains failures:

* check the newest directory under `ae/results/logs/` (timestamped),
* then check its subfolders/files (e.g., `table3/`, `table2a_*.txt`, etc.).
