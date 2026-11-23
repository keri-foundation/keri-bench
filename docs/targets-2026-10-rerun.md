# imbu 2c3b072 against Utah's targets: the rerun, November 2026

The first targets run ([`targets-2026-10.md`](targets-2026-10.md), imbu 670a3d8) found one thing under every volume verdict: an issuer's time per credential grew with its own KEL, about 0.65 ms a credential, and an issuer pushed past its capacity never drained. imbu-kel-growth answered both on `utah/next`. heti 04adc0f stops an issuance cloning the issuer's KEL and an anchor lookup walking it. imbu 44309be bounds each issuer's anchoring backlog and answers `503 e.env.saturated.r` with `Retry-After` past it. This report reruns the same targets with the same scenarios, rates, sizes, host and method, so that a difference in a number is the stack's (`this.i` 5frsx7pu). The targets are those of the first report, in its words.

Two things changed in the instrument, each recorded before the run that used it. The imbu adapter, now version 5, asks a saturated issuer again after its 503's `Retry-After`, as it already did for the answer budget's 429, and writes each issuer's answer counts to `imbu-answers.json` (`this.i` 7kmhh4wr). Target 3 was then run a second time on heti 980ee85, heti-consumer-kel, which landed during this rerun because of what the first pass of target 3 found (`this.i` 53kz99e2). In November, bench-revocation ran target 3 again on the stack utah/next then composed, imbu 7ff15e6a and heti 3a8b1ccb, and ran the stock fill again on heti 1e6839bc; both are added below, under targets 3 and 2 (`this.i` 8wsdm5fz).

## The verdicts

| target | first run (imbu 670a3d8) | this run (imbu 2c3b072) |
|---|---|---|
| 1. Peak hour, 2.8 a second | Fails at 1 issuer and at 3 | **Passes at 3 issuers**: 10,002 witnessed, p50 0.36 s, p99 0.49 s, flat to the end. **Fails at 1 issuer**, which now holds 1.4 a second for the whole window instead of collapsing. |
| 1. Office day, 0.35 a second | Fails at 1 issuer; passes at 3 for one day, falling behind on day 4 or 5 | **Passes at 1 issuer and at 3.** One issuer: 10,000 witnessed, p50 0.41 s, p99 1.87 s, where the first run collapsed at 4,036. Three issuers: p50 0.36 s, p99 0.48 s. Neither slowed with stock. |
| 2. Stock to a million | Storage linear; time per credential grew 0.76 ms a credential, crossing the office-day rate near 4,000 per KEL | Storage still linear, 12.9 KB a credential. **Time per credential no longer grows** to 10,165 in one KEL (p50 0.36 s at 10,000, against 7.9 s). A fill to 40,000 slowed fourfold past about 20,000, **outside imbu's stages**, and was stopped at 23,973. |
| 3. Revocation within 30 minutes | Not established: 9 of 100 measured | **Passes on imbu 7ff15e6a and heti 3a8b1ccb** (November, below): 100 of 100 recognised in 823–914 s, no registry gapped. Before that fix it failed narrowly on heti 980ee85, 94 of 96, the other 2 lost to an Observer gap (tick `~52qg`), and on heti 1ae3590 it was not established: 13 of 100 verified. |
| 4. Crash recovery | Every role ready in 3.7 s or less | No target. Every role ready again in 3.2 s or less, next success within 3.4 s of that; only in-flight credentials lost. An issuer holding 10,000 is ready in 9.4 s, against 10.8 s. |
| 5. HSM | 3 signatures a credential with Prefer: wait | 3.01, unchanged: 8.4 a second at the peak, against thousands a second. |

The finding under them: the issuer's own cost no longer grows with its KEL. What now limits the targets is outside imbu: heti's consumers (holder, verifier and Observer) for revocation, and, at a stock past about 20,000 in one KEL, something in the witnesses.

## Target 1: volume

### The peak hour, 2.8 a second

**Passes at three issuers.** The run offered 2.8 credentials a second open loop and stopped when 10,000 were witnessed, 59.5 minutes in. Requested to witnessed over all 10,002 was p50 0.355 s, p99 0.495 s, p99.9 1.40 s and max 1.94 s. No bucket of 200 had a p50 above 0.38 s, from the first credential to the last. No issuer answered a 503 or a 429. Each issuer issued 3,334.

| | first run, 3 issuers | this run, 3 issuers |
|---|---|---|
| witnessed | 2,000 of 10,080 offered | 10,002 of 10,002 |
| p50, first 200 | 0.39 s | 0.35 s |
| p50 at 1,700 | 1.25 s | 0.37 s |
| where it broke | about 1,900 credentials | it did not |
| anchored → witnessed, median | 0.12 s rising to 1.20 s | 0.10 s throughout |

**Fails at one issuer, but no longer collapses.** One issuer at 2.8 a second, for ten minutes as in the first run, witnessed 848 credentials inside the window, 1.41 a second, against 85 (0.14 a second) before. Requested to witnessed, for those that were witnessed, was p50 34 s and p99 88 s. That time is spent waiting: accepted to anchored had a median of 28 s, which is imbu's bounded backlog of 30 s of work, and anchored to witnessed only 0.28 s. Of the 1,680 offered, 730 were never witnessed. Each of those was asked again until its 60 s operation timeout and then given up. The issuer answered 3,086 of the adapter's sends with 503 `e.env.saturated.r`, and 48,205 with the answer budget's 429, as hundreds of in-flight operations shared four controllers' budgets. Every bucket of 200 ran at about the same rate. An issuer past its capacity at this imbu turns away what it cannot finish and keeps issuing at capacity, where 670a3d8 let its queue grow until requests aged past their signatures' freshness.

So one issuer's capacity is about 1.4 a second, half the peak-hour target, and three issuers carry the target with room to spare. On imbu 7b544ac and heti 093acb3, where a credential pays argon2 once, one issuer kept up with 4.0 a second in a one-minute probe ([`docs/argon2-2026-11.md`](argon2-2026-11.md)); for a full peak hour at 2.8 a second it witnessed 9,877 of the 10,000 the target asks for, losing 201 credentials to a stall of two to three minutes at each Registrar window ([the follow-ups](argon2-2026-11.md#the-follow-ups-21-november)). Three issuers were not pushed past 2.8 a second, so their headroom is not measured.

### The office day, 0.35 a second

**Passes at one issuer.** One issuer at 0.35 a second witnessed all 10,000 in 7.9 hours. Requested to witnessed was p50 0.41 s, p90 0.72 s, p99 1.87 s and max 12.7 s, and no request was refused for either budget or saturation. Per bucket of 200, p50 stayed between 0.35 and 0.53 s throughout, and p99 between 0.44 and 1.26 s except for one bucket at 9,100 credentials, where it was 8.7 s. The first run's issuer kept up for 4,036 credentials and then never recovered.

**Passes at three issuers.** At 0.35 a second between them, three issuers witnessed 10,001 in 7.9 hours, with p50 0.365 s, p99 0.483 s, p99.9 1.62 s and max 1.89 s. The first run's three issuers passed too, but p50 rose from 0.38 s to 2.41 s across the day, on course to fall behind on day 4 or 5. This run's did not rise. The same scenario on heti 980ee85 (target 3) gave p50 0.367 s and p99 2.12 s.

**Whether the office day holds past day 5 is not measured by a soak**, since each soak is one day. What bears on it is the stock evidence under target 2. Time per credential did not grow to 10,165 credentials in one KEL. The 40,000 fill held imbu's stages flat to about 22,000 in one KEL, but its fill rate fell from 1.4 a second to 0.3 past 22,000, for reasons outside imbu. Three issuers at the office day take 0.12 a second each, and their KELs reach 16,700 each by day 5, where the fill was still running at 0.85 to 1.03 a second. So on this evidence three issuers hold past day 5. At about 22,000 credentials per issuer, during day 7, an issuer's rate falls to about 0.3 a second, still more than twice what it needs, and how it behaves beyond 24,000 is not measured. One issuer takes 10,000 a day, reaches 20,000 on day 2 and passes 22,000 early on day 3, where 0.3 a second is less than the 0.35 it needs. So one issuer would plausibly fall behind on day 3, which the fill suggests and no soak has shown.

## Target 2: stock

**Storage is linear and issuance no longer grows with stock to 10,000. Past about 20,000 in one KEL, issuance slows, and the slowing is outside imbu's stages.** The curve comes from one issuer, as in the first run (`this.i` 4j5395l8): the office day at one issuer, empty to 10,000, and `stock-preseeded-1home`, a store filled with 10,000 and then offered 0.1 a second for 30 minutes with the issuer killed at 900 s. Both are fitted with `keri-bench growth` (`results/targets-2026-10-rerun/growth/imbu-2c3b072-1home.json`), 56 buckets from 100 to 10,165.

| | first run, imbu 670a3d8 | this run, imbu 2c3b072 |
|---|---|---|
| store bytes | 13.2 KB a credential, linear, R² 0.99999 | 12.9 KB a credential, linear, R² 0.99997 |
| at 10,000, 100,000, 1,000,000 | 132 MB, 1.3 GB, 13 GB | 129 MB, 1.3 GB, 12.9 GB |
| p50 requested → witnessed | 0.07 s + 0.76 ms a credential, R² 0.993 | no slope: R² 0.02, p50 0.36 s at 10,000 |
| p50 at 10,000, measured | 7.9 s | 0.36 s |
| where it crosses the office day's 2.86 s | 3,700–4,050 credentials | not within 10,165 |
| filling 10,000, 4 in flight | 14.1 hours | 1.6 hours |

The p99 fits are noise (R² 0.20 linear, 0.31 quadratic), driven by single slow buckets, and are not used.

The first run's curve answered where the wall was. This run's says only that there is none to 10,000. So the rerun planned a fill to 40,000 in one KEL, to measure four times further toward the million (`this.i` 4fsgrnre). That fill was stopped at 23,973, after 7.7 hours (`this.i` 59e73d45). Per 2,000 credentials, from its own timeline (`results/targets-2026-10-rerun/stock-preseeded-40k-1home`):

| credentials in the KEL | accepted → anchored | anchored → witnessed | witnessed → published | fill rate, 4 in flight |
|---|---|---|---|---|
| 0 | 1.82 s | 0.124 s | 0.504 s | 1.40 /s |
| 4,000 | 1.94 s | 0.136 s | 0.510 s | 1.47 /s |
| 8,000 | 2.36 s | 0.177 s | 0.517 s | 1.24 /s |
| 10,000 | 3.08 s | 0.237 s | 0.532 s | 0.91 /s |
| 14,000 | 1.80 s | 0.118 s | 0.491 s | 0.85 /s |
| 18,000 | 1.87 s | 0.113 s | 0.478 s | 0.87 /s |
| 20,000 | 1.90 s | 0.114 s | 0.488 s | 0.63 /s |
| 22,000 | 11.84 s | 0.129 s | 0.526 s | 0.31 /s |

imbu's own stages stayed flat to 22,000, yet the rate fell to a fifth. At the stop, one of the three witness processes held 8.4 GB resident and used 53% of a core, against 156 MB and 85 MB for the other two, and the host had 4 GB of 23 GB left. In the two runs that held 10,000 the witnesses never exceeded 160 MB (`rss-stock.log`, and the heti run's `rss.log`). So the growth past about 20,000 is most likely in the witnesses as one KEL grows, which heti-consumer-kel names as outside its change: every refresh still downloads the whole KEL from each witness it asks (bakobo/witness#43). This host has no profiler, so that is the likely cause, not a proven one. On disk at 23,973 the issuer's store held 307 MB (12.8 KB a credential, on the line above) and the three witnesses 212 MB.

What this means for a million: storage is not the constraint, at about 13 GB on one issuer's disk. Issuance per credential no longer grows with the issuer's own KEL. But a single KEL of 20,000 or more ran into a cost elsewhere, so a million in one issuer identifier is not supported by anything measured here, and spreading the stock across issuer identifiers remains the safe reading. Nothing past 23,973 in one KEL was measured, on either heti, and nothing about a million is extrapolated from the latency fits, which have no slope to extrapolate.

**The fill again on heti 1e6839bc, November.** heti witness-kel-growth (1e6839bc) was aimed at this slowdown: a refresh asks each witness only for the events it first saw since the last one. So the fill was run again on imbu 027ca678, heti 1e6839bc and the Registrar at b12a25e, from 11:28 UTC on 2 November, and stopped at 16:10 with 20,466 credentials witnessed, by the stopping rule set before it ran (`this.i` 5dychg9d, 5c8ks2lq): its fill rate had stayed under a third of its first 2,000's (`results/stock-2026-11`).

| credentials in the KEL | accepted → anchored | anchored → witnessed | witnessed → published | fill rate, 4 in flight |
|---|---|---|---|---|
| 0 | 1.67 s | 0.101 s | 0.484 s | 1.75 /s |
| 6,000 | 1.67 s | 0.105 s | 0.482 s | 1.75 /s |
| 10,000 | 1.69 s | 0.110 s | 0.486 s | 1.63 /s |
| 12,000 | 1.69 s | 0.110 s | 0.485 s | 1.72 /s |
| 14,000 | 1.72 s | 0.114 s | 0.493 s | 1.47 /s |
| 16,000 | 1.74 s | 0.112 s | 0.486 s | 0.80 /s |
| 18,000 | 1.81 s | 0.118 s | 0.496 s | 0.66 /s |
| 20,000 | 9.12 s | 0.608 s | 0.766 s | 0.26 /s |

**It did not remove the slowdown.** The fill ran faster than the October one before it broke, 1.75 a second against 1.40, flat to about 14,000, with imbu's stages flat to 18,000. Then the rate fell, from about 16,000 rather than 20,000. The same witness signature came with it. One of the three witness processes grew about 10 MB every 15 minutes, from 78 MB to 195 MB, until about 16,000 credentials, and then by 1.3 to 2.5 GB every 15 minutes, to 7.9 GB at its peak. The other two stayed under 200 MB, the Observer under 275 MB and the issuer under 340 MB (`results/stock-2026-11/rss.log`). The host had 4 GB of 23 GB left at the stop. So the cost that grows with one KEL is still in a witness, and its onset tracks that witness's memory. heti 1e6839bc marks one place where a witness still builds a KEL answer whole (heti tick `~3ylh`), which is where this points, unproven. It was not rerun on heti 3a8b1ccb, whose change is in the Observer, not the witness. On disk at 20,466 the issuer's store held 268 MB, 13.1 KB a credential, and the three witnesses 182 MB.

**The fill a third time, on the November fixes.** bench-stock ran the 40,000 fill on imbu e912ec4b and heti fc25249, which carry witness-kel-growth-2, heti-dead-lane and heti-lmdb-mapsize, and it witnessed 39,992 of 40,000 at 1.47 to 1.63 a second in every 2,000, with imbu's stages flat and no witness above 272 MB. So the slowdown under this target is gone to about 40,000. Its window then failed, because two witnesses' KEL stores reached keripy's default 100 MiB map at about 40,000 events. A 25-minute witness outage on the same stack left issuance at the office day's rate throughout. Both are in [`docs/stock-2026-11.md`](stock-2026-11.md).

**Restart at 10,000.** imbu killed at 900 s was ready again in 9.4 s, against 10.8 s, and completed its next credential 2.3 s after that, against 18.4 s. p50 was 0.36 s before and after, against 7.8 and 8.0 s. It lost the 1 credential in flight, against 2. One point again: restart time is not fitted against stock.

## Target 3: revocation freshness

**Fails, narrowly, on heti 980ee85: 94 of 96 revocations reached the verifier within 30 minutes, and 2 never did.** The office day at three issuers sends every 101st credential through delivery, presentation, verification and revocation, with the Registrar's 900 s window and verifier freshness of 900 s, so the design bound is the 30-minute target exactly, and recognition is polled every 10 s until two polls agree (`this.i` 8654nxrl, 2p4c5jhw).

It was run twice. On heti 1ae3590 the sample failed as it had in the first run. Verification timed out from credential 1,111 on, and the holder's admit from 2,121 on, because heti's lockbox fetched and replayed the issuer's whole KEL from a witness inside a 10 s deadline. The holder ended up answering `e.state.pending.observation.r` with its view of the issuer's key state up to 6,605 s old. 13 of 100 were verified and revoked, and 11 recognised, in 881–1,072 s. heti-consumer-kel fixed that for this target: a refresh of an issuer heti already holds now replays only the new events. The rerun on heti 980ee85 (`results/targets-2026-10-rerun-heti`) is the one this verdict rests on.

| | first run, heti 841fcbd | heti 1ae3590 | heti 980ee85 |
|---|---|---|---|
| sampled | 100 | 100 | 100 |
| stored by the holder | — | 21 | 96 |
| verified, and so revoked | 9 | 13 | 96 |
| recognised | 9 | 11 | 94 |
| requested → recognised | 872–927 s | 881–1,072 s | 307–1,228 s, p50 904, p90 916 |
| revoked but never recognised | 0 | 0 (2 more revocation requests timed out) | 2, revoked 3,263 s and 5,034 s before the run ended |

On heti 980ee85, revocation requested to published took p50 1.43 s and at most 4.80 s, imbu's part. The rest is the Registrar's window and the verifier's freshness. 64 of the 94 took over 900 s and 1 over 1,200 s. The worst, 1,228 s, leaves 572 s of margin.

**The two misses are the Observer's.** c007878 and c008686 were verified, then revoked. imbu published both revocations, and the Registrar holds the revoked chain for each (806 bytes). heti's Observer still held each one's issued chain (516 bytes) at the end of the run, with its per-registry gap flag set. Of the 96 registries the verifier met, those two are the only ones gapped, and the 94 recognised all hold the revoked chain in both stores. heti's Observer sets a registry's gap when it refuses that registry's head in a batch or holds it queued for KEL judgment, and clears it only when a later batch delivers a verified head for the same registry (heti `observer/store.py`, `apply` and `mark_queued`). A revoked credential's registry never changes again, so its gap never closes, and a verifier asking about it reads "not current" for as long as the Observer runs. The Observer's log does not say which of the two causes gapped them. This is heti's to fix, as tick `~52qg`. heti-observer-gap found the cause and landed a fix as heti 5623e2e as this report was being landed: the Observer kept heads it had refused retryably, here for the stale issuer key state above, in an in-memory queue capped at 64, and silently dropped any that did not fit, so a revocation dropped that way left its registry gapped for good. Refused heads now persist in the Observer's store and are retried (heti `this.i` @3prxc795). Before that fix, any revocation whose head an Observer once refused or queued was never recognised, so target 3 failed at any volume where that happened, which this run shows it did by about 2,600 credentials per issuer. The rerun on the fix is the next section.

The other four sampled credentials never reached revocation. Three deliveries, from credential 8,585 on, were refused `e.state.pending.observation.r`, with the issuer's key state 868 s old at the holder, so the holder's refresh still falls behind late in the day on 980ee85. One verification was refused `e.state.pending.registry.r` because the Observer did not yet hold the registry.

What this does not show:

- **96 is a moderate sample**, so the 94 bound the distribution's body, not its tail. Two misses in 96 is a rate of about 2%, with wide error.
- **Only the office day at three issuers.** At the peak rate, on heti 1ae3590, the holder could not refresh issuer key state within its 60 s bound, so nothing verified. The peak rate was not rerun on heti 980ee85.
- **Which deadline carried each recognition** is not separable here, since the Registrar's window and the verifier's freshness are both 900 s, as in the first run.

### On the fixed stack, November 2026

**Passes: every sampled revocation reached the verifier within 30 minutes, the slowest in 914 s, and no registry was left gapped.** bench-revocation reran office-day-3homes unchanged on the stack utah/next composed on 2 November: imbu 7ff15e6a, the heti 3a8b1ccb it pins, and the Registrar at bakobo/witness b12a25e, run from 16:23 UTC on 2 November to 00:41 on 3 November (`results/revocation-2026-11`, `this.i` 8wsdm5fz and its children). That is the result of record. heti 3a8b1ccb contains heti-observer-gap's fix (5623e2e) and witness-kel-growth's per-witness refresh (1e6839bc), repinned to heti 3a8b1ccb from 1e6839bc, and its Observer gathers on every batch again rather than judging against an issuer observation it already holds (heti `this.i` @6nwugfvw). The same scenario on 1e6839bc under imbu 027ca678, from 03:10 to 11:28 UTC on 2 November, is kept beside it as the comparison (`results/revocation-2026-11-heti-1e6839bc`).

| | heti 980ee85, imbu 2c3b072 | heti 1e6839bc, imbu 027ca678 | heti 3a8b1ccb, imbu 7ff15e6a, of record |
|---|---|---|---|
| sampled | 100 | 100 | 100 |
| delivered / stored / verified | 100 / 96 / 96 | 100 / 100 / 100 | 100 / 100 / 100 |
| revoked | 96 | 100 | 100 |
| recognised | 94 | 100 | 100 |
| requested → recognised | 307–1,228 s, p50 904, p90 916 | 822–914 s, p50 904, p90 911, mean 901.5 | 823–914 s, p50 904, p90 911, mean 901.8 |
| margin at the worst, of 1,800 s | 572 s | 886 s | 886 s |
| revoked but never recognised | 2 | 0 | 0 |
| registries gapped at the Observer at the end | 2 of 96 the verifier met; 9,876 of 10,001 held | 0; all 10,001 held | 0; all 10,001 held |
| stage failures | 4 | 0 | 0 |
| revocation requested → published | p50 1.43 s, max 4.80 s | p50 1.46 s, max 3.36 s | p50 1.44 s, max 4.26 s |
| proof generated → verified | — | p50 499 s, max 965 s | p50 498 s, max 971 s |
| Observer, peak resident memory | not sampled | 128 MB | 128 MB |
| issuance, requested → witnessed | p50 0.367 s, p99 2.12 s | p50 0.357 s, p99 0.465 s | p50 0.353 s, p99 0.456 s |

**Gathering on every batch did not change revocation latency.** Against 1e6839bc, whose Observer judged a batch against an issuer observation it already held, 3a8b1ccb's minimum moved by 1 s, its p50, p90 and maximum not at all, and its mean by 0.3 s, all under the 10 s at which recognition is polled. 80 of the 100 took over 900 s, against 83. Recognition lands just past one of the two 900 s deadlines, the Registrar's window or the verifier's freshness, and the gathering is not on that path for long enough to show. Its cost would show instead in the Observer's work per batch, which this run measures only as memory, the same 128 MB peak in both; the Observer's CPU was not sampled.

Revocation requested to published, imbu's part, took p50 1.44 s and at most 4.26 s. Verification itself, proof generated to verified, took p50 498 s and up to 971 s, because a fresh credential is not current at the verifier until the Registrar's window delivers its registry. That is the design, and inside the verifier's 1,200 s deadline. At the end, the Observer's store held every registry the Registrar did, 10,001, none gapped, and each of the 100 the verifier met carried the revoked chain in both stores. Tick `~52qg` is closed.

What changed between the first and last columns is more than the Observer fix. heti moved from 980ee85 to 3a8b1ccb, imbu from 2c3b072 to 7ff15e6a (imbu-bulk-overlap, imbu-review-followups and Tier C's held SMAID, none on the plain issuance or revocation path this scenario drives, then the heti pin), and the Registrar from witness ed1dcfc to b12a25e, which re-pins its own keripy. So the result is the deployed stack's, not the Observer fix's alone. That the two misses' cause is gone is shown by the store, not only by the count: no registry is gapped.

What this does not show:

- **100 is still a moderate sample.** No miss in 100 bounds a miss rate at about 3% with 95% confidence, not at zero.
- **One run of record, at the office day, at three issuers.** The peak rate was not rerun for revocation.
- **Three runs on the way were stopped and are not reported**: on heti 5623e2e under imbu 2c3b072 at 2,426 credentials, and on heti 1e6839bc under imbu 2c3b072 at 571, each when the PM moved the pins, and one on 3a8b1ccb two minutes in, because the report's draft was uncommitted and the run would have named a dirty harness (`this.i` 5dychg9d, 0v5zd44x, 5c8ks2lq).

## Target 4: crash recovery

**No verdict, since Utah has given no target. Every role is ready again within 3.2 s of being killed, the next credential completes within 3.4 s of that, and no crash loses more than the credentials in flight.** These are the first run's twelve crash scenarios, unchanged (`results/targets-2026-10-rerun/crash-*`). Each kills one target at 20 s of a 60 s window and restarts it on its own disk. All 36 runs were accepted. Ranges are across three repetitions, p50 and p99 are requested to verified, and the fates are summed over the three.

| crashed | issuers | ready s | first success s | p50 before s | p50 after s | p99 after s | done / resumed / lost |
|---|---|---|---|---|---|---|---|
| imbu (every issuer) | 1 | 1.28–1.39 | 2.66–3.34 | 2.22–2.56 | 3.08–3.16 | 4.00–4.39 | 102 / 3 / 3 |
| imbu issuer h0 of 3 | 3 | 1.28–1.31 | 2.19–2.41 | 1.93–2.26 | 2.45–2.65 | 3.76–4.33 | 102 / 3 / 3 |
| one witness of 3 | 1 | 1.03–1.07 | 0.10–1.20 | 2.43–2.45 | 3.18–3.29 | 4.13–4.63 | 102 / 6 / 0 |
| one witness of 3 | 3 | 1.02–1.08 | 0.38–1.05 | 2.06–2.32 | 2.43–2.58 | 4.04–4.14 | 102 / 6 / 0 |
| all three witnesses | 1 | 3.03–3.09 | 1.80–3.17 | 2.39–2.53 | 3.14–3.40 | 4.03–4.74 | 99 / 9 / 0 |
| all three witnesses | 3 | 3.00–3.20 | 0.91–1.09 | 2.32–2.37 | 2.32–2.62 | 3.50–4.19 | 99 / 9 / 0 |
| Registrar and Observer | 1 | 2.40–2.89 | 1.08–1.59 | 2.24–2.35 | 3.29–3.31 | 3.94–4.45 | 99 / 9 / 0 |
| Registrar and Observer | 3 | 2.53–2.78 | 1.08–1.47 | 2.36–2.42 | 2.43–2.60 | 3.57–4.22 | 98 / 10 / 0 |
| holder | 1 | 1.04–1.13 | 0.23–3.24 | 2.30–2.51 | 3.02–3.26 | 4.00–4.81 | 102 / 2 / 4 |
| holder | 3 | 0.96–1.13 | 0.94–3.14 | 1.90–2.29 | 2.41–2.58 | 3.58–4.08 | 102 / 3 / 3 |
| verifier | 1 | 0.94–1.15 | 0.94–1.64 | 2.40–2.52 | 3.03–3.24 | 4.29–4.68 | 102 / 6 / 0 |
| verifier | 3 | 0.93–1.09 | 0.90–1.60 | 2.20–2.32 | 2.44–2.54 | 3.64–4.21 | 101 / 7 / 0 |

Against the first run, every time to ready is within a few tenths of a second of what it was, and losses are the same: one credential in flight per repetition for a crashed imbu, and the same handful for a crashed holder. The issuer's first success at three issuers is 2.19–2.41 s against 2.96–3.43 s, and comes, as before, from the issuers that never stopped. The first run also read h0's own first success from the timelines. This report did not, so that column has no counterpart here. As before, every one of these restarts a store holding a few dozen credentials. The restart at 10,000 is under target 2.

## Target 5: HSM headroom

**3.01 signatures a credential with a waiting client, unchanged.** One profile was rerun, a signer per issuer at 15 ms per signature, three issuers at 2.8 a second, three 120 s repetitions (`results/targets-2026-10-rerun/hsm-15ms-wait-3homes`). Each issuer's signer signed 3.01 times per issuance over 112 issuances: 2 for each credential itself (the ixn anchoring its registry and the grant), 1 signed answer, and the one answer resolving the holder before the window opened. The signer's median was 15.22 ms against 15.24 ms before. Requested to witnessed was p50 0.355–0.366 s and p99 0.440–0.457 s, against 0.43 s and 0.52–0.58 s.

So the peak-hour target needs 8.4 signatures a second across the deployment, and the office day 1.1. A device doing a thousand a second has about 120 times the peak's need. imbu-kel-growth did not change what a credential costs an HSM, and the polling client's 6.6 signatures a credential from the first run still stands, since it was not rerun. The first run's caveats hold: the profile is simulated, and only issuance is counted.

## Measured on

All on kelun, the first run's host: a shared 8-core host with 23 GB of RAM, Linux 7.0.0-38, Python 3.14, every stack under a named `systemd-run --user` unit at nice 19 with `LimitNOFILE=524288`. No other worker's stack was seen on the host during these windows. Each run's provenance records the host's load before, during and at the end of its window, and `loadavg.log` in each results directory has it every 60 s. Windows ran at load 1.6 to 2.8, most of it each run's own stack. Runs were serialised, the 40,000 fill included, so no two stacks shared the host.

| what | commit |
|---|---|
| imbu | 2c3b07271f22e490dfac74ced5948fbcf1d0f311 (utah/next, with imbu-kel-growth 44309be, imbu-scale 7c74df5 and delegated-issuers 2c3b072) |
| heti, targets 1, 2, 4 and 5 | 1ae3590fd829848061c8c01b75ff7977332fc52b (what imbu 2c3b072 pins, with heti-kel-growth 04adc0f) |
| heti, target 3 | 980ee85084abfd310c515f01df4c3869fc78894a (heti-consumer-kel, overriding imbu's pin; `this.i` 53kz99e2) |
| keripy | 910dcb350e63d3129c91345429c1fa10f2dae5e5 (bakobo fork, through heti) |
| witness (Registrar) | ed1dcfc563ebff6545738f820d7410043dcbfbce |
| harness, peak hour, HSM, crash and the office day at 3 issuers | 58df2a9 |
| harness, office day at 1 issuer | 477013a |
| harness, stock at 10,000 | afa7dfa |
| harness, the 40,000 fill | 477013a |
| imbu, November | 027ca6780fbd33a571b570555a93adc94419e9e9 (the 1e6839bc comparison and the second fill); 7ff15e6ada507c462a740633d5f16c92cc34470d (target 3 of record) |
| heti, November | 1e6839bc77028271b44551108cd154b2d08f2d27 and 3a8b1ccb17e1c29b79aafb191cb16cde35e2727b, each what that imbu pins |
| witness (Registrar), November | b12a25e293e46b8a0febe180ca19f38cdbeeec3e |
| harness, November | ec8d431 (target 3 on 1e6839bc, and the second fill); b90119c (target 3 of record) |
| harness, target 3 on heti 980ee85 | 571ccdb |

Between 58df2a9 and afa7dfa only `this.i` and a scenario file changed, and 571ccdb differs from them only in heti's pin. imbu-scale did not narrow `_bulk_lock` (heti tick `~7ssy`), so bulk concurrency per issuer is unchanged, and no bulk scenario was rerun. Delegated issuers do not change the topology: every issuer here incepts its own undelegated issuing identifier. The first calibration on the target-3 harness failed one interval's p99 by 62 ms in one repetition, run straight after the stacks test suite, and was rerun clean before the run. The failed one is kept beside it (`calibration-failed-20261101T0417`).

## What this does not measure

- **More than one host.** As before, every party ran on one machine over loopback.
- **More than 23,973 credentials in one KEL on the stacks this report measured**, or a measured window above 10,000. The 40,000 fill was stopped (target 2), and a million is not extrapolated. On the November fixes a fill witnessed 39,992 of 40,000 ([`docs/stock-2026-11.md`](stock-2026-11.md)).
- **Why the fill slowed past 20,000, or why one witness grew to 8.4 GB.** Both are observed, and the witnesses are the likely place, but this host allows no profiler.
- **The office day past its first day.** Each soak is one day. The claim that three issuers hold past day 5 is read from the stock fill, not from a soak.
- **Targets 1, 2, 4 and 5 on the November stack.** Only target 3, and the 40,000 fill under target 2, were rerun on imbu 027ca678 and heti 1e6839bc.
- **Three issuers past 2.8 a second.** They carried the peak with p99 under half a second, but their ceiling was not probed.
- **Repetitions for the long runs.** As before, the peak hour, office day and stock runs ran once each. The crash and HSM runs have three repetitions each.

## Reproduce

```
uv sync --extra stacks
systemd-run --user --unit=keri-bench-targets -p LimitNOFILE=524288 --nice=19 \
    -E PATH="$PATH" -E HOME="$HOME" --working-directory="$PWD" \
    scripts/targets.sh runs/targets results/targets-2026-10-rerun scenarios/targets/<name>.toml ...
uv run keri-bench growth results/targets-2026-10-rerun/office-day-1home/rate-0.35/rep-1/report.json \
    results/targets-2026-10-rerun/stock-preseeded-1home/rate-0.1/rep-1/report.json \
    --at 10000 --at 100000 --at 1000000 --bound-s 2.857 --out growth.json
```

Targets 1, 2, 4 and 5 ran at this repository's pins before heti 980ee85 was merged (commit 58df2a9 and its `uv.lock`). Target 3's rerun is the tree at 571ccdb. Each result directory has the run's timeline, provenance, report and, from adapter version 5, `imbu-answers.json`, and `SHA256SUMS` covers them all. Timelines over 1 MB are gzipped.
