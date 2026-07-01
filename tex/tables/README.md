# Tables handoff contract

This directory holds `.tex` table fragments generated from
`results/h1/aggregate.csv`, intended to be `\input`'d directly from
section files (e.g., `05_experimental_setup.tex`, `06_results.tex`).

## Expected pipeline

Once `results/h1/aggregate.csv` exists, a (not-yet-written) generation
script produces one `.tex` fragment per table, each containing a
complete `tabular` environment (or `\begin{table}...\end{table}` block)
ready to `\input`. Suggested filenames:

| Expected filename here        | Content                                          |
|--------------------------------|---------------------------------------------------|
| `experiment_matrix.tex`        | Replaces the placeholder table in `05_experimental_setup.tex` (`tab:experiment-matrix`) |
| `h1_summary.tex`                | Summary stats (p50/p99/p99.9, hotspot metric) per (policy, load) |

This directory intentionally has no generation script yet — that work
happens once the H1 sweep produces `results/h1/aggregate.csv` (see
`tracecxl_experiment_spec.md` Section 5 for the schema).
