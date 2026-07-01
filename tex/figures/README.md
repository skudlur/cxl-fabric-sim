# Figures handoff contract

This directory holds figures referenced by `tex/sections/06_results.tex`.
It is empty (aside from this file) until the H1 sweep completes.

## Expected pipeline

Once `results/h1/plots/*.png` (or whatever format the analysis scripts
in `src/analysis/plots.py` produce) exist, copy or symlink them here
under the following names, matching what `06_results.tex` expects:

| Expected filename here      | Source                                    | Referenced in                  |
|------------------------------|--------------------------------------------|---------------------------------|
| `latency_cdf.pdf`            | `results/h1/plots/` latency CDF plot        | Fig. `fig:latency-cdf`          |
| `p99_vs_load.pdf`             | `results/h1/plots/` p99-vs-load plot        | Fig. `fig:p99-vs-load`          |
| `hotspot_vs_load.pdf`         | `results/h1/plots/` hotspot-metric-vs-load  | Fig. `fig:hotspot-vs-load`      |

LaTeX/`\includegraphics` will happily take PDF, PNG, or JPG — prefer PDF
or high-res PNG for print quality. If the analysis scripts only emit
PNG, that's fine; just update the extension in both this table and the
corresponding `\includegraphics` call in `06_results.tex`.

Until a given file exists here, its `\includegraphics` line in
`06_results.tex` stays commented out — do not point `\includegraphics`
at a nonexistent file, since a missing-figure error should fail the
build loudly rather than being silently skipped.
