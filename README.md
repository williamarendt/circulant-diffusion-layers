# Circulant Diffusion Layers: Code and Experimental Records

Code accompanying **Circulant Diffusion Layers: Cost Bounds and Rectangle Reuse**.
The directories follow the paper's experimental subsections. In directory names,
`B` denotes the branch number, `w` the row and column weight, and `Fp` an odd prime
field. The rectangle-packing experiments use **Gurobi** and **HiGHS
(through SciPy)**. The supplementary general-circuit experiments use
BP-family C++ heuristics and a locally implemented signed Paar-style Python
heuristic, with independent matrix and circuit verification.

| Directory | Setting | Main entry points |
|---|---|---|
| [sec3.1.4_F2_B4_w3](sec3.1.4_F2_B4_w3/README.md) | Binary field, weight three, branch number four | `verify_weight_three_appendix.py` |
| [sec3.2.2_F2_B6_w5](sec3.2.2_F2_B6_w5/README.md) | Binary field, weight five, branch number six | `search_weight5_small.py`, `compare_weight5_families.py` |
| [sec4.1.4_Fp_B4_w3](sec4.1.4_Fp_B4_w3/README.md) | Odd prime fields, weight three, branch number four | `verify_section41.py` |
| [sec4.2.4_Fp_B5_w4](sec4.2.4_Fp_B5_w4/README.md) | Odd prime fields, weight four, branch number five | `audit_section424.py` |
| [sec4.3.2_Fp_B6_w5](sec4.3.2_Fp_B6_w5/README.md) | Odd prime fields, weight five, branch number six | `run_odd_weight5_remaining.py`, `run_odd_weight5_power_two.py` |
| [suppA.3_F2_Cg](suppA.3_F2_Cg/README.md) | Supplement A.3: binary BP/RNBP/A1/A2 experiments, weights three and five | `verify_results.py`, `run_small.py`, `run_large.py` |
| [suppB.1_Fp_B5_w4_Cg](suppB.1_Fp_B5_w4_Cg/README.md) | Supplement B.1: odd prime fields, weight four, branch number five | `verify_results.py`, `run_search.py` |
| [suppB.3_Fp_B6_w5_Cg](suppB.3_Fp_B6_w5_Cg/README.md) | Supplement B.3: odd prime fields, weight five, branch number six | `verify_results.py`, `run_search.py` |
| [common](common/README.md) | Shared algorithms, solver interfaces, and basic tests | `circrect/` |

## Directory layout

```text
code1_github/
  sec3.1.4_F2_B4_w3/    Section code, README, results/
  sec3.2.2_F2_B6_w5/    Section code, README, results/, auxiliary/
  sec4.1.4_Fp_B4_w3/    Section code, README, results/
  sec4.2.4_Fp_B5_w4/    Section code, README, results/
  sec4.3.2_Fp_B6_w5/    Section code, README, results/, reference/
  suppA.3_F2_Cg/         Binary general circuits, recorded logs, witnesses, figure
  suppB.1_Fp_B5_w4_Cg/   Signed general circuits, recorded logs, witnesses
  suppB.3_Fp_B6_w5_Cg/   Signed general circuits, recorded logs, witnesses
  common/               Shared code, dependencies, notebooks, tests
  docs/                 Source hashes and solver inventory
  historical/           Earlier source snapshots and organization notes
```

Saved results are in each section's `results/` directory. The `gurobi/`
subdirectory contains the original batches; some cases use analytical formulas
without invoking a solver. Batch dates are retained for traceability.
`common/original_batch_metadata/` contains summary metadata for the original
batches spanning multiple sections.

Each section's `run_gurobi.py` invokes the shared search program. The supplementary
SciPy scripts are also retained. Entry points automatically load `common`, so the
shared algorithms need not be duplicated. See the [solver inventory](docs/solver_inventory.json)
for historical solver information.

## Getting started

Run commands from the root of this directory with a Python environment containing
the dependencies needed for the selected task:

The new supplementary directories can verify their saved results with Python's
standard library alone. Repeating the binary searches also requires a C++11
compiler. Each directory README gives commands and the recorded time budgets;
fresh searches always write to a new output directory. Complete trial logs are
losslessly compressed, while table witnesses are directly readable. The two Fp
directories each contain a frozen copy of their small shared implementation so
each chapter can be downloaded and checked on its own.

```sh
python -m pip install -r common/requirements-scipy.txt
# For Gurobi searches, also install the Gurobi dependencies and use a valid license.
python -m pip install -r common/requirements-gurobi.txt

# Check file hashes, Python/notebook syntax, and local import paths.
python -X utf8 common/check_bundle.py

# Preview cases without starting a solver.
python -X utf8 sec4.2.4_Fp_B5_w4/run_gurobi.py --n-values 8 --primes 5 --dry-run
```

For the shared tests, change to `common/` and run:

```sh
python -m unittest tests.test_circrect tests.test_closed_form tests.test_notebook tests.test_storage
```

Read the section README before running an experiment: some verification scripts
regenerate saved audit files. Use a new output directory for fresh optimization
runs. Historical status fields retain their original scope; an incomplete search
is not relabeled as complete.

This English distribution was copied from the Chinese working bundle `code1`.
Comments, documentation, notebook text, and display messages have been translated.
The algorithms and numerical experimental results are unchanged. Historical paths
in saved records describe the original runs; use the layout above to locate the
files in this distribution. See [provenance documentation](docs/README.md) for
original and translated-file hashes. The paper's exhaustive experiments have not
been rerun as part of this translation.
