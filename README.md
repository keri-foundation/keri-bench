# keri-bench

[![CI](https://github.com/bakobo/keri-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/bakobo/keri-bench/actions/workflows/ci.yml)

A measurement instrument for end-to-end KERI+ACDC issuance on any implementation: the State of Utah's KERI-006 (load and soak tests covering throughput, persistence, concurrency, restart recovery, witnessing, TEL replay and wallet delivery). It drives a stack open-loop through per-role adapters, puts a fault proxy in front of every link, and writes a raw timeline from which every reported number can be recomputed. Why it is built this way is in [`this.i`](this.i); what it measures and how its own correctness is tested is in [`docs/test-plan.md`](docs/test-plan.md).

## The results

The runs are read in the write-ups, each of which states what was measured, on which versions, and what it showed:

- [Against Utah's targets: the rerun, November 2026](docs/targets-2026-10-rerun.md) has the most recent verdicts on Utah's targets for volume, stock, revocation, crash recovery and HSM sizing.
- [One issuer after the argon2 fix, November 2026](docs/argon2-2026-11.md) measures one issuer's capacity before and after heti stopped paying argon2 twice per credential: from about 1.5 a second to between 5 and 6, with three issuers past 12 and one issuer's full peak hour stalling at each Registrar window.
- [Stock and witness outage, November 2026](docs/stock-2026-11.md) fills a single issuer to 40,000 credentials and takes a witness down for 25 minutes.
- [Against Utah's targets, October 2026](docs/targets-2026-10.md) is the first measurement against those targets, before the fixes it led to.
- [Baseline, October 2026](docs/baseline-2026-10.md) and [its second part](docs/baseline-2026-10-part2.md) measured the stack before Utah had given targets, including how many signatures a credential costs an HSM.

The [glossary](docs/glossary.md) defines the terms these pages use, and [reading a run report](docs/reading-a-report.md) explains the raw per-run reports the write-ups cite as evidence.

All of this, with every committed run's report, is published at <https://bakobo.github.io/keri-bench/>; [`docs/site.md`](docs/site.md) says how the site is built.

## From a fresh clone to passing tests

You need Linux (the harness names its clock by the kernel's boot id), [uv](https://docs.astral.sh/uv/), and nothing else; uv fetches Python 3.14.

```
git clone https://github.com/bakobo/keri-bench && cd keri-bench
uv sync
uv run pytest
```

The suite includes the calibration, which runs the synthetic stack for about a minute and a half. `uv run pytest -m "not calibration"` skips it while you iterate; CI never does.

## Using it

```
uv run keri-bench calibrate --out runs/calibration
uv run keri-bench run scenarios/contract-synthetic.toml --out runs/smoke --rate 10 \
    --calibration runs/calibration/calibration.json
uv run keri-bench contract scenarios/contract-synthetic.toml --out runs/contract
uv run keri-bench report runs/smoke/rate-10/rep-1
```

`run` without `--rate` sweeps every load step and repetition in the scenario and writes `sweep.json` with the saturation point. Each run directory holds `timeline.jsonl`, `provenance.json`, `report.json` and `report.md`; `report` rebuilds the last two from the first two.

- **The driver holds a core.** It yields to the event loop continuously so sends leave on time, and a run whose driver fell behind is refused rather than reported.
- **Calibrate on the machine you measure on.** `calibrate` proves the harness recovers known delays, a known throughput cap and an injected stall. Its error budget goes into every run given `--calibration`, and a run without one says so. The default `--gate strict` holds the two-sided bars; `--gate bounds` checks only what a loaded host cannot move, which is what CI uses, and `--replay DIR` judges a recorded calibration without timing anything (`this.i` 0hykugwr).
- **Every knob is explicit.** A scenario that leaves an adapter's knob unset is refused.
- **Soaks.** A scenario's `[soak]` table (`bucket`, `per_credentials`, `sample_s`) adds a drift section to the report: each full bucket's p50 and p99 and their least-squares slopes against store size, elapsed time and bytes on disk (`this.i` 7f9jfc99). `[stop] credentials` ends the schedule once that many credentials reach the measure's end, and `[preseed]` (`credentials`, `concurrency`) fills the store through the stack before the window opens (`this.i` 9yx6cg92).
- **Crashes.** A crash fault names a role, or one of its processes as `<role>.<process>`, such as `witness_pool.w0` or `issuer.h1`.

## The imbu stack

The real stack's adapters need private bakobo repositories, so they are an extra: `uv sync --extra stacks`, then `uv run pytest tests/stacks`. That stands up the whole stack, a witness pool of real keripy witnesses, the Registrar and heti's Observer for state distribution, imbu as the issuer, and heti as holder and verifier, and drives several credentials, each in its own registry, through their whole lifecycle. `scenarios/imbu-smoke.toml` is the KERI-006 smoke run at one issuer, against imbu's asynchronous operations. `scenarios/baseline/` holds the October 2026 baseline, which `scripts/baseline.sh` runs and collects (how to run it is at the top of the script), and whose results and reading are in [`docs/baseline-2026-10.md`](docs/baseline-2026-10.md). `scenarios/hsm-sweep/` signs imbu's principal through heti's throttled external signer, and `scenarios/bulk/` drives imbu's SEDI proofed bulk ceremony through the `imbu.bulk_issuer` adapter; their results are in [`docs/baseline-2026-10-part2.md`](docs/baseline-2026-10-part2.md). `scenarios/targets/` measures imbu 670a3d8 against Utah's stated targets, which `scripts/targets.sh` runs and collects, and `keri-bench growth` fits store size and latency against stock; the verdicts are in [`docs/targets-2026-10.md`](docs/targets-2026-10.md), and the rerun against imbu 2c3b072, before and after, is [`docs/targets-2026-10-rerun.md`](docs/targets-2026-10-rerun.md). `uv run python -m keri_bench.stacks.microbench --out <file>` times keripy's Ed25519 and Blake3-256 on the host. Each milestone's binding on this stack, and its known gaps, are in [`docs/adapters.md`](docs/adapters.md). The `Stacks` workflow runs all of this weekly.

## Layout

- `src/keri_bench/`: the harness. The modules are `driver`, `run`, `timeline`, `clocks`, `stats`, `proxy`, `procs`, `report`, `reconcile`, `calibration` and `contract`.
- `src/keri_bench/adapters/`: the per-role adapter interface and the registry of adapter names.
- `src/keri_bench/synthetic/`: the calibration stack and its adapters.
- `src/keri_bench/stacks/`: the imbu stack's processes and adapters.
- `scenarios/`: scenario files.
- `tests/golden/`: hand-checked timelines for every timeline schema the harness has emitted.
- `tools/site_source.py`, `scripts/site-source` and `zensical.toml`: the documentation site's build; `tools/glossary.py` and `scripts/glossary` write the glossary from `docs/glossary.toml`, and `tools/rerender.py` and `scripts/rerender-reports` re-render the committed run reports; see [`docs/site.md`](docs/site.md).

## License

Apache-2.0; see [`LICENSE`](LICENSE). [`CONTRIBUTING.md`](CONTRIBUTING.md) says how a change lands, and [`SECURITY.md`](SECURITY.md) how to report a vulnerability.
