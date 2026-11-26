# Supplementary material B.3: Fp general circuits

Weight 5, branch number 6. `results/table.csv` reproduces the
comparison in supplementary material B.3. Gate counts are verified upper
bounds; exact rectangle minima are retained when better. The `all` scope has
no connectivity requirement. Large-order `connected` and `depth3` witnesses
are included separately; independent-copy extensions remain disconnected.

## Files

- `src/signed_paar.py`: original signed Paar-style optimizer, unchanged.
- `src/verify_circuit.py`: independent exact coefficient-vector verification.
- `src/algebra_snapshot.py`: exact matrix checks, frozen from the experiment.
- `src/small_worker.py`, `src/large_worker.py`: original task functions, with
  only local import/path setup replaced for this chapter directory.
- `run_search.py`: portable driver; requires a **new** output directory.
- `results/small/`, `results/large/`: recorded jobs, protocols, candidate checks,
  states, saved circuits and audited summaries. Trial logs are losslessly
  compressed in `trial_logs.zip` to keep uploads manageable.
- `witnesses/`: matrix (full first row and matrix), circuit, characteristic,
  gate count and depth for each reported upper bound; `manifest.json` maps
  each witness to its recorded source. Integer circuits reused across fields
  are checked again in the reported field.

## Verify without searching

From the repository root, using Python 3.10 or newer (standard library only):

```sh
python suppB.3_Fp_B6_w5_Cg/verify_results.py
python suppB.3_Fp_B6_w5_Cg/verify_results.py --properties
```

The second command also rechecks matrix invertibility and branch number.

## Repeat searches

Recorded budgets: 300 seconds per order/prime through order16, and 600 seconds
at orders32/64; all arithmetic/depth arms share that task budget. The exact
original seeds, tie choices, candidate counts and source hashes are in the
recorded jobs/protocols/logs. Finishing a timed heuristic is not an optimality
proof. Completed attempts vary with the machine and concurrent load.

```sh
python suppB.3_Fp_B6_w5_Cg/run_search.py --stage small --orders 10 --primes 3 --out /tmp/fp_small_repeat
python suppB.3_Fp_B6_w5_Cg/run_search.py --stage large --orders 32 --primes 5 --out /tmp/fp_large_repeat
```

Choose platform-appropriate new paths for `--out` (for example `repeat_fp_small`
on Windows). Use `--workers 8` for the recorded concurrency or `--seconds 2`
for a short functionality check. Omit orders/primes to run all feasible cells
in that stage. Fresh results go only to `--out`; recorded results stay intact.
The fresh worker results are direct per-task results retaining their initial
baselines; the published table additionally uses audited cross-field integer
reuse and independent-copy extensions. Those final witnesses are supplied.

Historical source-path strings in protocol/state files refer to the original
run. They are provenance, not runtime dependencies. No SAT/MILP solver or
third-party Python package is needed for these general-circuit heuristics.

For browser upload, recorded task files are losslessly packed in `results/small/task_records.zip` and `results/large/task_records.zip`. The verifier reads these archives directly; the search driver unpacks them automatically when needed. No results or circuit contents have changed.
