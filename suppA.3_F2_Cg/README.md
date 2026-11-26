# Supplementary material A.3: binary general circuits

BP, RNBP, A1 and A2 experiments for binary weight-three/branch-four and
weight-five/branch-six circulants. The algorithms are from Tan and Peyrin's
XORreduce author code, snapshot `200f743`, with the original MIT notice in
`THIRD_PARTY_LICENSE.txt`. Source adapters for dimensions up to32 and up to64
are included in `src/`; the latter uses unsigned64-bit signals.
No compiled binary is distributed.

## Recorded results and witnesses

- `results/small_combined_results.csv`: all small-order table bounds.
- `results/small_records.zip`: original candidates, protocols, all35,217
  trials and their SLP circuits (including weight-three experiments).
- `results/large_records.zip`: original per-task states/logs and all6,829
  completed circuits from the 60 fixed-budget large-order tasks.
- `results/large_jobs.json`, `large_sample.json`, `large_protocol.json`:
  exact selected supports, selection rule, algorithms and budgets.
- `results/n32_candidates.json`, `n64_candidates.json`: complete legal-class
  enumeration, from which the fixed stratified sample was selected.
- `witnesses/manifest.json`: first-row support, gate count, depth and SLP
  filename for retained small-order gate/depth witnesses and the80/160-gate
  disconnected lifts. A circulant's rows are cyclic right shifts of its
  first row; the support completely specifies the binary matrix.
- `figures/`: the paper's four-panel n13--16 figure, its CSV and metadata.
  Each plotted minimum aggregates all legal classes at that order.

Verify **all** recorded circuits, selected witnesses and1,200 plotted values,
without compiling or searching (Python3.10+, standard library only):

```sh
python suppA.3_F2_Cg/verify_results.py
```

The saved figure PDF/PNG requires no plotting dependency to view. To redraw
the same curves from the included CSV, install matplotlib and run:

```sh
python -m pip install matplotlib
python suppA.3_F2_Cg/plot_seed_progress.py --out repeat_seed_figure
```

## Compile and repeat

From repository root, with a C++11 compiler:

```sh
g++ -std=c++11 -O2 suppA.3_F2_Cg/src/bp_small.cpp -o suppA.3_F2_Cg/src/bp_small
g++ -std=c++11 -O2 suppA.3_F2_Cg/src/bp_large.cpp -o suppA.3_F2_Cg/src/bp_large
python suppA.3_F2_Cg/run_small.py --cases 10:5:6 --seeds 100 --out repeat_binary_small
python suppA.3_F2_Cg/run_large.py --orders 32,64 --workers 8 --out repeat_binary_large
```

On Windows compile to `bp_small.exe` and `bp_large.exe`. Use `--executable`
to specify another location. Both drivers require a new output directory
and never overwrite recorded results. Small-order cases accept
`n:weight:branch` triples separated by commas. The recorded cases are
weight3:4,5,6,7,8,9,15,21,27; weight5:10,11,12,13,14,15,16.

Small protocol: BP once per canonical legal support; RNBP/A1/A2 each100
seeds,60s timeout per complete construction. Large protocol:10 preselected
supports per order (8 connected/2 disconnected), RNBP/A1/A2 only,3600s per
order32 matrix/algorithm and7200s at order64;90 task-hours total. Seeds
advance after completed constructions and each construction may consume
the remaining task budget. Use `--seconds 1 --limit-tasks 1` on run_large.py
for a short functionality check. Timed results depend on machine/load.

Only the wrapper paths, CLI and fresh-output handling differ from the
recorded task functions. Historical paths in saved metadata are provenance,
not dependencies. Heuristic completion and affine matrix-class enumeration
do not prove circuit optimality. Depth<=3 bounds filter the stored circuits;
they are not results of a depth-constrained exact optimizer.
