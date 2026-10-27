# `docs/report/figures/` — generator output only

The report's figures are **not** here. `docs/report/main.tex` includes them as
`\includegraphics{../figures/NAME.png}`, which from `docs/report/` resolves to **`docs/figures/`**; that is where
every figure the chapters use lives, and the authoritative figure documentation is `docs/figures/README.md`.

This directory holds only raw generator output: `c2b_mode_shape_corrected.pdf` and `c2b_mode_shape_corrected.png`,
written straight to their hard-coded paths by `tools/host/mode_plot/mode_plot.py`. No `.tex` file includes them —
the chapter uses the copies `docs/figures/mode_shape_corrected.{pdf,png}` and
`docs/figures/mode_shape_mispaired_before.{pdf,png}`, which are byte-identical to their sources.
