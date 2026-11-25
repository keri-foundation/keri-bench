"""``report.json`` and ``report.md``, derived from the timeline and the provenance only.

Nothing here reads live state, so a disputed number can be recomputed from a run directory
(this.i 8q4myzru; test plan, Outputs). Every latency goes through the one named percentile
definition in ``stats`` (HDR, three significant digits, quoted as the bucket's upper bound), and
every interval through ``clocks.interval``, so a cross-domain interval without a measured offset
is reported as not measured rather than computed (this.i 7vsky4sk).
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

from . import provenance as provenance_file
from .clocks import Clocks, Interval, NotMeasured, interval
from .driver import check_driver
from .errors import BenchError
from .reconcile import classify, summary
from .stats import Histogram, drift
from .timeline import Event, Header, read_timeline
from .vocabulary import ISSUANCE_CHAIN, MILESTONES, PAIRS, REVOCATION_CHAIN, Pair

REPORT_SCHEMA = 1
NOT_MEASURED = "not measured"
PERCENTILES: tuple[tuple[str, int | float], ...] = (("p50", 50), ("p90", 90), ("p99", 99),
                                                    ("p99.9", 99.9))
RUN_FIELDS = ("rate", "repetition", "warmup_s", "lag_limit_ms", "measure", "stages")
DRIVER = {"adapter": "driver", "role": "harness", "method": "observed", "clock": "harness",
          "resolution_ns": 1}
"""The driver writes ``requested`` itself, so it is observed even when no adapter declares it."""

E_WINDOW = "e.input.missing.timeline.window.f"
E_RUN = "e.input.missing.provenance.run.f"
E_MEASURE = "e.input.range.provenance.measure.f"
E_WARMUP = "e.input.range.provenance.warmup.f"
E_REQUESTS = "e.input.missing.timeline.requested.f"
E_REQUESTED_CLOCK = "e.input.range.timeline.requested.clock.f"


class _Run:
    """One run's timeline and provenance, indexed for the sections that read them."""

    def __init__(self, header: Header, events: list[Event], record: dict) -> None:
        self.header, self.events, self.record = header, events, record
        self.clocks = Clocks.from_events(header.harness_clock, events)
        self.run = record["run"]
        missing = [name for name in RUN_FIELDS if name not in self.run]
        if missing:
            raise BenchError(E_RUN, f"The provenance's run section lacks {missing}, so the "
                             f"report cannot say what was offered or measured.")
        measure = self.run["measure"]
        if not (isinstance(measure, list) and len(measure) == 2
                and all(name in MILESTONES for name in measure)):
            raise BenchError(E_MEASURE, f"The run's measure must name a start and an end "
                             f"milestone, and {measure!r} does not.")
        self.measure: tuple[str, str] = (measure[0], measure[1])
        self.start = self._first_harness_event("run_started").t
        self.end = self._first_harness_event("run_ended").t
        self.warmup = round(self.run["warmup_s"] * 1_000_000_000)
        self.measured_from = self.start + self.warmup
        if self.measured_from >= self.end:
            raise BenchError(E_WARMUP, f"The warmup of {self.warmup} ns is as long as the "
                             f"{self.end - self.start} ns window, so nothing was measured.")
        self.first: dict[str, dict[str, Event]] = defaultdict(dict)
        for event in events:
            for credential in event.credentials:
                seen = self.first[credential].get(event.name)
                if seen is None or event.t < seen.t:
                    self.first[credential][event.name] = event
        self.requested: dict[str, int] = {}
        for credential, names in sorted(self.first.items()):
            if "requested" in names:
                mapped = self.clocks.to_harness(names["requested"])
                if mapped is None:
                    raise BenchError(E_REQUESTED_CLOCK, f"{credential} was requested on "
                                     f"{names['requested'].clock}, which has no offset to the "
                                     f"harness clock, so its latency has no start.")
                self.requested[credential] = mapped[0]
        if not self.requested:
            raise BenchError(E_REQUESTS, "The timeline has no requested event, so there is "
                             "nothing to report.")
        self.window = [c for c, t in self.requested.items()
                       if self.measured_from <= t < self.end]
        self.observed = {event.name for event in events}

    def _first_harness_event(self, name: str) -> Event:
        found = [event for event in self.events if event.name == name]
        if not found:
            raise BenchError(E_WINDOW, f"The timeline has no {name} event, so the measured "
                             f"window is unknown.")
        return min(found, key=lambda event: event.t)

    def harness_t(self, event: Event) -> int | None:
        mapped = self.clocks.to_harness(event)
        return None if mapped is None else mapped[0]

    def samples(self, credentials: Iterable[str], start: str,
                end: str) -> tuple[list[Interval | NotMeasured], int]:
        results, missing = [], 0
        for credential in credentials:
            names = self.first[credential]
            if start not in names:
                continue
            if end not in names:
                missing += 1
                continue
            results.append(interval(names[start], names[end], self.clocks))
        return results, missing


def _reported(result: Interval) -> int:
    # reported() leaves a 1 ns-resolution negative alone; a report never shows one.
    return max(0, result.reported())


def _summarise(results: Sequence[Interval | NotMeasured], missing: int) -> dict:
    histogram, reasons, unmeasured, resolution = Histogram(), set(), 0, None
    for result in results:
        if isinstance(result, NotMeasured):
            unmeasured += 1
            reasons.add(result.reason)
            continue
        histogram.record(_reported(result))
        resolution = max(resolution or 0, result.resolution_ns)
    out: dict[str, Any] = {"count": histogram.count, "missing": missing,
                           "not_measured": {"count": unmeasured, "reasons": sorted(reasons)},
                           "resolution_ns": resolution, "measured": histogram.count > 0}
    if histogram.count:
        for key, p in PERCENTILES:
            out[key] = histogram.percentile(p)
        out["max"] = histogram.max
    return out


def _key(start: str, end: str) -> str:
    return f"{start}->{end}"


def _intervals(run: _Run) -> dict:
    specs: dict[str, list[str]] = {}
    for pair in PAIRS:
        for start, end in pair.intervals:
            specs.setdefault(_key(start, end), []).append(pair.key)
    specs.setdefault(_key(*run.measure), [])
    for chain in (ISSUANCE_CHAIN, REVOCATION_CHAIN):
        seen = [name for name in chain if name in run.observed or name == "requested"]
        for start, end in zip(seen, seen[1:]):
            specs.setdefault(_key(start, end), [])
    for name in MILESTONES:
        if name != "requested" and name in run.observed:
            specs.setdefault(_key("requested", name), [])
    out = {}
    # A cold sync is one per verifier, not one per credential, so its events name the sync rather
    # than any requested credential (pair 5, initial synchronization).
    syncs = sorted({c for c, names in run.first.items() if "sync_full_started" in names})
    for key, pairs in specs.items():
        start, end = key.split("->")
        entry = {"start": start, "end": end, "pairs": pairs}
        entry.update(_summarise(*run.samples(syncs if start == "sync_full_started"
                                             else run.window, start, end)))
        out[key] = entry
    return out


def _censored(run: _Run) -> dict:
    """Credentials lacking the measure end are censored at the window's end: a lower bound."""
    start, end = run.measure
    samples: list[tuple[int, bool]] = []
    incomplete = []
    for credential in run.window:
        names = run.first[credential]
        if end in names:
            if start in names:
                result = interval(names[start], names[end], run.clocks)
                if isinstance(result, Interval):
                    samples.append((_reported(result), False))
            continue
        incomplete.append(credential)
        begin = run.harness_t(names[start]) if start in names else None
        if begin is not None:
            samples.append((max(0, run.end - begin), True))
    out: dict[str, Any] = {"count": len(incomplete), "credentials": sorted(incomplete)}
    if not samples:
        out["latency"] = {"measured": False}
        return out
    histogram = Histogram()
    for value, _ in samples:
        histogram.record(value)
    # At a tie the censored sample sorts last: its true value is at least the recorded one.
    ordered = sorted(samples)
    latency: dict[str, Any] = {"count": len(samples), "censored": sum(c for _, c in samples)}
    for key, p in PERCENTILES:
        rank = math.ceil(Fraction(str(p)) * len(ordered) / 100)
        latency[key] = {"value": histogram.percentile(p), "lower_bound": ordered[rank - 1][1]}
    latency["max"] = {"value": histogram.max, "lower_bound": ordered[-1][1]}
    out["latency"] = latency
    return out


def _driver(run: _Run) -> dict:
    credentials = sorted(run.requested)
    dispatched = []
    for credential in credentials:
        event = run.first[credential].get("dispatched")
        dispatched.append(None if event is None else run.harness_t(event))
    limit = round(run.run["lag_limit_ms"] * 1_000_000)
    verdict = check_driver([run.requested[c] for c in credentials], dispatched,
                           lag_limit_ns=limit)
    return {"ok": verdict.ok, "p99_lag_ns": verdict.p99_lag_ns, "backlog": verdict.backlog,
            "reason": verdict.reason, "lag_limit_ns": limit}


def _throughput(run: _Run) -> dict:
    span = run.end - run.measured_from
    milestones = {}
    for name in MILESTONES:
        events = [names[name] for names in run.first.values() if name in names]
        if not events:
            continue
        count = unconvertible = 0
        for event in events:
            t = run.harness_t(event)
            if t is None:
                unconvertible += 1
            elif run.measured_from <= t < run.end:
                count += 1
        milestones[name] = {"count": count, "per_s": count * 1_000_000_000 / span,
                            "unconvertible": unconvertible}
    pairs = {pair.key: {name: milestones.get(name, {}).get("per_s")
                        for name in pair.throughput}
             for pair in PAIRS if pair.throughput}
    return {"window_ns": span, "offered_per_s": run.run["rate"], "milestones": milestones,
            "pairs": pairs}


def _fault_windows(run: _Run) -> list[dict]:
    ends = sorted((e for e in run.events if e.name == "fault_ended"), key=lambda e: e.t)
    used: set[int] = set()
    found = []
    for start in sorted((e for e in run.events if e.name == "fault_started"),
                        key=lambda e: e.t):
        attrs = start.attrs or {}
        kind, target = attrs.get("kind"), attrs.get("target")
        ended = None
        for i, end in enumerate(ends):
            other = end.attrs or {}
            if i not in used and end.t >= start.t and (other.get("kind"),
                                                      other.get("target")) == (kind, target):
                used.add(i)
                ended = end.t
                break
        found.append({"kind": kind, "target": target, "started_ns": start.t,
                      "ended_ns": ended})
    return found


def _faults(run: _Run, windows: list[dict]) -> list[dict]:
    start_name, end_name = run.measure
    out = []
    for window in windows:
        began = window["started_ns"]
        until = run.end if window["ended_ns"] is None else window["ended_ns"]
        groups: dict[str, list[str]] = {"before": [], "during": [], "after": []}
        for credential in run.window:
            t = run.requested[credential]
            groups["before" if t < began else "during" if t < until else "after"].append(
                credential)
        entry = dict(window)
        for phase, members in groups.items():
            entry[phase] = _summarise(*run.samples(members, start_name, end_name))
        if window["kind"] == "crash":
            entry.update(_recovery(run, window["target"], began))
        out.append(entry)
    return out


def _process_event(run: _Run, name: str, process: str, after: int) -> Event | None:
    found = [e for e in run.events if e.name == name and e.t >= after
             and (e.attrs or {}).get("process") == process]
    return min(found, key=lambda e: e.t) if found else None


def _recovery(run: _Run, target: str, began: int) -> dict:
    """A crash's target is a process, or a role whose processes are ``<role>.<name>`` (this.i
    5ed29j5w). It is ready once every process it killed is ready again, so time to ready runs
    from the first kill to the last of those readies. The first success is any credential's,
    not only one the crashed process served (~76aw)."""
    out: dict[str, int | None] = {"time_to_ready_ns": None, "time_to_first_success_ns": None}
    names = {(e.attrs or {}).get("process") for e in run.events if e.name == "process_killed"}
    kills = [kill for name in sorted(n for n in names if n == target
                                     or str(n).startswith(target + "."))
             if (kill := _process_event(run, "process_killed", name, began)) is not None]
    if not kills:
        return out
    readies = [_process_event(run, "process_ready", (kill.attrs or {})["process"], kill.t)
               for kill in kills]
    if any(ready is None for ready in readies):
        return out
    ready_t = max(ready.t for ready in readies)
    out["time_to_ready_ns"] = ready_t - min(kill.t for kill in kills)
    successes = [t for e in run.events if e.name == run.measure[1]
                 for t in [run.harness_t(e)] if t is not None and t >= ready_t]
    if successes:
        out["time_to_first_success_ns"] = min(successes) - ready_t
    return out


def _matrix(run: _Run) -> dict:
    declared: dict[str, dict] = {}
    for role, declaration in run.record["adapters"].items():
        for name, seen in declaration.get("milestones", {}).items():
            declared.setdefault(name, {"adapter": declaration["adapter"], "role": role,
                                       "method": seen["method"], "clock": seen["clock"],
                                       "resolution_ns": seen["resolution_ns"]})
    declared.setdefault("requested", dict(DRIVER))
    counts: dict[str, int] = defaultdict(int)
    for event in run.events:
        counts[event.name] += 1
    return {name: {**declared[name], "events": counts[name]} if name in declared
            else "unobserved" for name in MILESTONES}


def _domain(run: _Run, matrix: dict, name: str) -> str:
    for event in run.events:
        if event.name == name:
            return event.clock
    clock = matrix[name]["clock"]
    if clock == "harness":
        return run.header.harness_clock
    return run.record["clocks"].get(clock, clock)


def _gaps(run: _Run, matrix: dict, names: Sequence[str],
          intervals: Iterable[tuple[str, str]], harness_bound: Iterable[str]) -> list[str]:
    gaps = [f"No adapter in this run observes {name}." for name in names
            if matrix[name] == "unobserved"]
    if gaps:
        return gaps

    def unmeasured(name: str) -> str | None:
        domain = _domain(run, matrix, name)
        if domain == run.header.harness_clock or domain in run.clocks.offsets:
            return None
        return (f"{name} is stamped in {domain}, which has no offset to the harness clock "
                f"measured in this run.")

    found = [unmeasured(name) for name in harness_bound]
    for start, end in intervals:
        if _domain(run, matrix, start) != _domain(run, matrix, end):
            found += [unmeasured(start), unmeasured(end)]
    found = list(dict.fromkeys(gap for gap in found if gap))
    if found:
        return found
    # Declared and measurable in principle, but a pair is measured only if it was in this run,
    # and an interval only if one credential has both of its ends.
    missing = [f"{name} is declared, but no {name} event appeared in this run."
               for name in names if name not in run.observed]
    def paired(start: str, end: str) -> bool:
        # The credentials the interval tables count: the measured window, or a cold sync.
        pool = run.window if start != "sync_full_started" else run.first
        return any(start in run.first[c] and end in run.first[c] for c in pool)

    return missing or [f"No credential in the measured window has both {start} and {end}."
                       for start, end in intervals if not paired(start, end)]


def _ordered(pair: Pair) -> list[str]:
    names = [name for interval_ in pair.intervals for name in interval_]
    return list(dict.fromkeys(names + list(pair.throughput or ())))


def _observability(run: _Run, faults: list[dict]) -> dict:
    matrix = _matrix(run)
    pairs = {}
    for pair in PAIRS:
        if pair.intervals or pair.throughput:
            gaps = _gaps(run, matrix, _ordered(pair), pair.intervals, pair.throughput or ())
        else:
            gaps = _gaps(run, matrix, run.measure, [run.measure], ())
            if not faults:
                gaps.append("No fault was scheduled in this run, so there is no faulted "
                            "performance to set beside normal performance.")
        pairs[pair.key] = {"measurable": not gaps, "gap": " ".join(gaps) or None}
    return {"milestones": matrix, "pairs": pairs}


def _failures(events) -> dict:
    """Lifecycle stages that failed, by stage and code, and a scheduled fault that could not be
    applied, which refuses the run: its numbers would describe a fault that never happened."""
    stages: dict[str, int] = {}
    codes: dict[str, int] = {}
    fault_failed = None
    for event in events:
        attrs = event.attrs or {}
        if event.name == "stage_failed":
            # Attributes are whatever the timeline says, so they are named as text.
            stage, code = str(attrs.get("stage", "?")), str(attrs.get("code", "?"))
            stages[stage] = stages.get(stage, 0) + 1
            codes[code] = codes.get(code, 0) + 1
        elif event.name == "fault_failed" and fault_failed is None:
            fault_failed = (f"The scheduled {attrs.get('kind')} fault on {attrs.get('target')} "
                            f"could not be applied: {attrs.get('error')}")
    return {"count": sum(stages.values()), "by_stage": stages, "by_code": codes,
            "fault_failed": fault_failed}


def _exits(events) -> list[dict]:
    """Role processes that exited when the harness had not stopped them (this.i 9zgpyjxt). The
    run is degraded, not refused: its numbers describe a stack that lost a role at a known
    moment, and the reader is told which and when."""
    return [{**(event.attrs or {}), "t": event.t} for event in events
            if event.name == "process_exited"]


def _exit_sentence(entry: dict) -> str:
    return (f"The run is degraded. The {entry.get('process', '?')} process (pid "
            f"{entry.get('pid', '?')}) exited with code {entry.get('code', '?')} at "
            f"{entry.get('at', '?')} (harness t {entry['t']} ns), and the harness did not stop "
            f"it, so everything measured after that moment ran on a stack without it.")


def _preseed(run: _Run, declared: dict | None) -> tuple[dict | None, str | None]:
    """What the timeline says the preseed did, and why the run is refused if it did not fill
    the store the run declared before the window opened (this.i 9yx6cg92): more than one
    record, a record off the harness clock, a record of an undeclared preseed or none of a
    declared one, counts that are not
    whole numbers or not possible, a count short of the declaration, a failure, or a preseed
    that finished after the window opened. preseed_started and the declaration's own type are
    not checked (~2ac4)."""
    seeded = [e for e in run.events if e.name == "preseed_ended"]
    wanted = declared.get("credentials") if isinstance(declared, dict) else None
    unknown = "so the store the soak started from is unknown."
    tail = "so the soak did not start from the store it declared."
    if len(seeded) > 1:
        return None, (f"The timeline records {len(seeded)} preseeds where a run has at most "
                      f"one, {unknown}")
    if not seeded:
        if wanted is None:
            return None, None
        return None, (f"The run declared a preseed of {wanted} credentials and its timeline "
                      f"records none, {tail}")
    if seeded[0].clock != run.header.harness_clock:
        return None, (f"The preseed's record is on the clock {seeded[0].clock}, not the "
                      f"harness's, so when it finished is unknown.")
    attrs = seeded[0].attrs or {}
    requested, failed = attrs.get("requested"), attrs.get("failed")
    if type(requested) is not int or type(failed) is not int:
        return None, (f"The preseed's counts are not whole numbers ({requested!r} requested, "
                      f"{failed!r} failed), {unknown}")
    if requested < 0 or not 0 <= failed <= requested:
        return None, (f"The preseed's counts are not possible ({requested} requested, {failed} "
                      f"failed), {unknown}")
    preseed = {"requested": requested, "failed": failed}
    if wanted is None:
        return preseed, (f"The timeline records a preseed of {requested} credentials the run "
                         f"never declared, {tail}")
    if requested != wanted:
        return preseed, (f"The run declared a preseed of {wanted} credentials and its timeline "
                         f"records {requested} requested, {tail}")
    if failed:
        return preseed, (f"The preseed asked for {requested} credentials and {failed} failed, "
                         f"{tail}")
    if seeded[0].t >= run.start:
        return preseed, f"The preseed finished after the measured window opened, {tail}"
    return preseed, None


PROFILE_TOLERANCE = 0.05
"""The test plan's HSM self-check: measured latency and rate within 5% of the profile."""
UNTHROTTLED_MS = 1.0
"""With no latency configured, a signer's median operation must take under this."""


def _signer_census(entry: dict) -> tuple[dict, str | None]:
    """One signer's census and profile check (this.i 2p26rn9h). Each operation is
    ``[kind, requested_ns, started_ns, finished_ns]`` on the harness's clock: asked for, given
    its start by the device's cap, and done after its latency."""
    ops = entry["operations"]
    counts: dict[str, int] = {}
    for kind, *_ in ops:
        counts[kind] = counts.get(kind, 0) + 1
    signatures = counts.get("sign", 0)
    issued = entry["issuances"]

    configured = entry["latency_ms"]
    # A profile must be one a device could have: finite, a latency not negative, a rate above
    # zero, and counts that are whole and not negative.
    finite = (all(v is None or (type(v) in (int, float) and math.isfinite(v))
                  for v in (configured, entry["rate"]))
              and (configured is None or configured >= 0)
              and (entry["rate"] is None or entry["rate"] > 0)
              and all(type(n) is int and n >= 0
                      for n in (entry["signed_responses"], entry["issuances"]))
              and all(type(t) is int for op in ops for t in op[1:]))
    # Every inception is signed once as well, which is the identifier's, not any credential's.
    other = (signatures - entry["signed_responses"] - counts.get("incept", 0)) if finite else 0
    median = (round(statistics.median(f - s for _, _, s, f in ops) / 1e6, 3) if ops else None)
    if median is None or not finite:
        latency_ok = False
    elif configured is None:
        latency_ok = median < UNTHROTTLED_MS
    else:
        latency_ok = abs(median - configured) <= PROFILE_TOLERANCE * configured
    rate = entry["rate"]
    rate_out: dict[str, Any] = {"configured_per_s": rate, "exercised": False, "ok": True}
    # An operation was held by the cap when it asked before the device's next start was free.
    starts = sorted((s, r) for _, r, s, _ in ops)
    gap = 0 if rate is None or not finite else 1e9 / rate
    spacings = [s - before for (before, _), (s, r) in zip(starts, starts[1:])
                if r < before + gap]
    if rate is not None and spacings and finite:
        spacing = round(statistics.median(spacings) / 1e6, 3)
        want = 1000.0 / rate
        rate_out = {"configured_per_s": rate, "exercised": True, "median_spacing_ms": spacing,
                    "ok": abs(spacing - want) <= PROFILE_TOLERANCE * want}
    out = {"counts": counts, "signed_responses": entry["signed_responses"],
           "other_signatures": other,
           "per_issuance": other / issued if finite and issued else None,
           # What an HSM signs per credential, polls and all: the rate a device must carry
           # is this times the issuance rate (this.i 5k8z0pxe).
           "issuances": issued,
           "signatures_per_issuance": ((signatures - counts.get("incept", 0)) / issued
                                       if finite and issued else None),
           "refused_answers": entry.get("refused_answers"),
           "latency": {"configured_ms": configured, "median_ms": median, "ok": latency_ok},
           "rate": rate_out}
    accounted = other >= 0 and finite
    out["ok"] = latency_ok and rate_out["ok"] and accounted
    problems = []
    if not finite:
        problems.append(f"latency {configured!r} ms, rate {rate!r} and counts "
                        f"{entry['signed_responses']!r} and {entry['issuances']!r} are not a "
                        f"finite profile a device could have")
    if other < 0:
        problems.append(f"the record holds {entry['signed_responses']} signed answers but only "
                        f"{signatures} signatures, so it cannot account for them")
    if not latency_ok:
        against = ("none configured, which allows under 1 ms" if configured is None
                   else f"{configured} ms configured, more than 5% off")
        seen = "not seen" if median is None else f"{median} ms"
        problems.append(f"latency median {seen} against {against}")
    if not rate_out["ok"]:
        problems.append(f"rate spacing median {rate_out['median_spacing_ms']} ms against "
                        f"{1000.0 / rate} ms, more than 5% off")
    return out, "; ".join(problems) or None


def _census(record: dict) -> tuple[Any, str | None]:
    """The signer census per role, from what each adapter reported after the drain; the run is
    refused when any signer missed its profile (test plan, HSM sensitivity)."""
    if "census" not in record:
        return NOT_MEASURED, None
    out: dict[str, Any] = {"ok": True}
    reason = None
    for role, section in record["census"].items():
        signers = []
        for index, entry in enumerate(section["signers"]):
            checked, problem = _signer_census(entry)
            signers.append(checked)
            if problem and reason is None:
                reason = (f"The signer's profile check failed for {role} signer {index}: "
                          f"{problem}.")
        # Whatever else the adapter counted, such as a registry pool, is carried as it said.
        out[role] = {**{k: v for k, v in section.items() if k != "signers"},
                     "signers": signers}
        out["ok"] = out["ok"] and all(s["ok"] for s in signers)
    return out, reason


def _census_md(census: Any) -> list[str]:
    if census == NOT_MEASURED:
        return ["The signer census is not measured: no adapter in this run signs through an "
                "external signer it can count.", ""]
    lines = ["| role | signer | operations | signed responses | other signatures | per "
             "issuance | latency median | rate |", "|---|---|---|---|---|---|---|---|"]
    for role, section in census.items():
        if role == "ok":
            continue
        for index, s in enumerate(section["signers"]):
            counts = ", ".join(f"{k} {v}" for k, v in sorted(s["counts"].items()))
            lat = s["latency"]
            configured = "none" if lat["configured_ms"] is None else lat["configured_ms"]
            latency = (f"{lat['median_ms']} ms ({configured} configured) "
                       f"{'ok' if lat['ok'] else 'FAILED'}")
            rate = s["rate"]
            rate_text = ("not exercised" if not rate["exercised"] else
                         f"{rate['median_spacing_ms']} ms spacing "
                         f"({1000.0 / rate['configured_per_s']} configured) "
                         f"{'ok' if rate['ok'] else 'FAILED'}")
            lines.append(f"| {role} | {index} | {counts} | {s['signed_responses']} | "
                         f"{s['other_signatures']} | {s['per_issuance']} | {latency} | "
                         f"{rate_text} |")
    return lines + [""]


DRIFT_AXES = {"store_credentials": None, "elapsed": 3600.0, "store_bytes": float(1 << 20)}
"""Each axis a soak's drift is fitted on, with the x-unit its slope is quoted per: the soak's
per_credentials for store size, an hour for elapsed time, a MiB for bytes on disk."""


def _fit(points: list[tuple[float, float]], per: float) -> dict:
    try:
        fitted = drift([x for x, _ in points], [y for _, y in points])
    except BenchError as unfit:
        return {"measured": False, "reason": unfit.message}
    return {"measured": True, "slope_ns": fitted.slope * per, "low_ns": fitted.low * per,
            "high_ns": fitted.high * per, "n": fitted.n}


def _drift(run: _Run, preseed: dict | None) -> dict:
    """A soak's drift (this.i 7f9jfc99): the window's credentials in request order, cut into
    full buckets; each bucket's p50 and p99 of the measure interval; and the slope of each on
    store size, elapsed time and bytes on disk at the bucket's middle credential."""
    soak = run.run["soak"]
    size, per = soak["bucket"], soak["per_credentials"]
    preseeded = 0 if preseed is None else preseed["requested"] - preseed["failed"]
    samples = sorted((e.t, e.attrs["bytes"]) for e in run.events if e.name == "footprint")
    stale = round(2 * soak["sample_s"] * 1e9) if "sample_s" in soak else None
    ordered = sorted(run.window, key=lambda c: run.requested[c])
    start, end = run.measure
    buckets = []
    for first in range(0, len(ordered) - size + 1, size):
        members = ordered[first:first + size]
        middle = first + size // 2
        at = run.requested[ordered[middle]]
        results, missing = run.samples(members, start, end)
        histogram = Histogram()
        for result in results:
            if isinstance(result, Interval):
                histogram.record(_reported(result))
        # A size older than two sampling intervals is stale, not this bucket's size.
        before = [b for t, b in samples if t <= at and (stale is None or at - t <= stale)]
        buckets.append({
            "index": len(buckets), "credentials": histogram.count, "missing": missing,
            "store_credentials": preseeded + middle,
            "elapsed_s": (at - run.measured_from) / 1e9,
            "store_bytes": before[-1] if before else None,
            "p50_ns": histogram.percentile(50) if histogram.count else None,
            "p99_ns": histogram.percentile(99) if histogram.count else None})
    slopes = {}
    for quantile in ("p50", "p99"):
        slopes[quantile] = {}
        for axis, unit in DRIFT_AXES.items():
            key = "elapsed_s" if axis == "elapsed" else axis
            points = [(b[key], b[f"{quantile}_ns"]) for b in buckets
                      if b[f"{quantile}_ns"] is not None and b[key] is not None]
            slopes[quantile][axis] = _fit(points, per if unit is None else unit)
    return {"bucket": size, "per_credentials": per, "preseeded": preseeded,
            "buckets": buckets, "slopes": slopes,
            "units": {"store_credentials": f"per {per} credentials", "elapsed": "per hour",
                      "store_bytes": "per MiB"}}


def _drift_md(out: dict) -> list[str]:
    lines = ["## Soak drift", "",
             f"Buckets of {out['bucket']} credentials in request order, on a store preseeded "
             f"with {out['preseeded']}. Each slope is a least-squares fit of the bucket "
             f"percentile with a 95% Student t interval.", "",
             "| percentile | axis | slope | 95% low | 95% high | buckets |",
             "|---|---|---|---|---|---|"]
    for quantile, axes in out["slopes"].items():
        for axis, fit in axes.items():
            unit = out["units"][axis]
            if fit["measured"]:
                lines.append(f"| {quantile} | {unit} | {round(fit['slope_ns'])} ns | "
                             f"{round(fit['low_ns'])} ns | {round(fit['high_ns'])} ns | "
                             f"{fit['n']} |")
            else:
                lines.append(f"| {quantile} | {unit} | not measured: {fit['reason']} | | | |")
    lines += ["", "| store credentials | elapsed s | store bytes | completed | missing | p50 "
              "| p99 |", "|---|---|---|---|---|---|---|"]
    for b in out["buckets"]:
        lines.append(f"| {b['store_credentials']} | {b['elapsed_s']} | {b['store_bytes']} | "
                     f"{b['credentials']} | {b['missing']} | {_ns(b['p50_ns'])} | "
                     f"{_ns(b['p99_ns'])} |")
    return lines + [""]


def _warnings(run: _Run, driver: dict, intervals: dict) -> list[str]:
    out = []
    for item in provenance_file.untested(run.record["adapters"], run.record["components"]):
        tested = item["tested"] or "no version of it"
        out.append(f"The {item['role']} adapter {item['adapter']} ran against "
                   f"{item['component']} {item['running']}, which it was never "
                   f"contract-tested against (it was tested against {tested}).")
    if not driver["ok"]:
        out.append(f"The run is refused. {driver['reason']}")
    for key, entry in intervals.items():
        skipped = entry["not_measured"]
        if skipped["count"]:
            out.append(f"The interval {key} was not measured for {skipped['count']} "
                       f"credential(s) because of its clock evidence. "
                       + " ".join(skipped["reasons"]))
    return out


def derive(timeline_path: Path, provenance_path: Path, *, generator_commit: str) -> dict:
    header, events = read_timeline(timeline_path)
    record = provenance_file.read(provenance_path)
    run = _Run(header, events, record)
    driver = _driver(run)
    intervals = _intervals(run)
    windows = _fault_windows(run)
    reconciliation: Any = NOT_MEASURED
    if "reconciliation" in record:
        section = record["reconciliation"]
        spans = [(w["started_ns"], run.end if w["ended_ns"] is None else w["ended_ns"])
                 for w in windows]
        outcomes = classify(events, section["verifier"], section["anchors"], faults=spans)
        reconciliation = {"summary": summary(outcomes),
                          "credentials": {c: outcomes[c].to_dict() for c in sorted(outcomes)}}
    failures = _failures(events)
    preseed, preseed_failed = _preseed(run, run.run.get("preseed"))
    census, census_failed = _census(record)
    refused = driver["reason"] if not driver["ok"] else (failures["fault_failed"]
                                                         or preseed_failed or census_failed)
    out = {
        "report_schema": REPORT_SCHEMA, "generator_commit": generator_commit,
        "timeline_schema": header.timeline_schema,
        "vocabulary_version": header.vocabulary_version,
        "harness_commit": header.harness_commit, "scenario_sha256": record["scenario_sha256"],
        "run": run.run,
        "window": {"start_ns": run.start, "end_ns": run.end, "warmup_ns": run.warmup,
                   "measured_from_ns": run.measured_from, "credentials": len(run.window)},
        "driver": driver, "refused": refused is not None, "refused_reason": refused,
        "failures": failures,
        "measure": _key(*run.measure), "intervals": intervals, "incomplete": _censored(run),
        "throughput": _throughput(run), "observability": _observability(run, windows),
        "faults": _faults(run, windows), "reconciliation": reconciliation,
        "measurement_cost": record.get("measurement_cost", NOT_MEASURED),
        "census": census, "warnings": _warnings(run, driver, intervals),
    }
    if "soak" in run.run:
        out["drift"] = _drift(run, preseed)
    if preseed is not None:
        out["preseed"] = preseed
    if preseed_failed:
        out["warnings"].append(f"The run is refused. {preseed_failed}")
    if census_failed:
        out["warnings"].append(f"The run is refused. {census_failed}")
    if failures["fault_failed"]:
        out["warnings"].append(f"The run is refused. {failures['fault_failed']}")
    exits = _exits(events)
    if exits:
        out["degraded"] = True
        out["unexpected_exits"] = exits
        out["warnings"] += [_exit_sentence(entry) for entry in exits]
    if failures["count"]:
        out["warnings"].append(f"{failures['count']} lifecycle stage(s) failed: "
                               f"{failures['by_stage']}, with codes {failures['by_code']}.")
    # Provenance written before calibration existed has no section, and its report is unchanged.
    if "calibration" in record:
        out["calibration"] = record["calibration"]
        out["warnings"] += _calibration_warnings(record["calibration"], header.harness_commit)
    return out


def _calibration_warnings(calibration: Any, harness_commit: str) -> list[str]:
    if not isinstance(calibration, dict):
        return ["The run carries no calibration, so its numbers have no measured error budget "
                "(test plan, Part B #1). Run keri-bench calibrate and pass --calibration."]
    out = []
    if not calibration["ok"]:
        out.append("The calibration this run carries did not pass, so its error budget does not "
                   "show that the harness measures correctly.")
    elif calibration.get("gate", "strict") != "strict":
        out.append("The calibration this run carries passed only the bounds gate, which checks "
                   "what a loaded host cannot move; its error budget was not held to the "
                   "two-sided bars. Calibrate on this host with --gate strict.")
    if calibration["harness_commit"] != harness_commit:
        out.append(f"The calibration was made by harness {calibration['harness_commit']}, not "
                   f"by {harness_commit}, which made this run.")
    return out


# --- markdown ----------------------------------------------------------------------------------

def _figures(x: float) -> str:
    """Three significant figures, never in exponent form."""
    if x != 0 and -1 < x < 1:
        # 0.014 and 0.010 must not both read 0.01, 0.9999 reads 1.00 and -0.0012 keeps its
        # magnitude (the hostile pass on #7).
        return f"{x:#.3g}"
    if x >= 100:
        return f"{x:.0f}"
    if x >= 10:
        return f"{x:.1f}"
    return f"{x:.2f}"


def _ns(value: int | None) -> str:
    """A duration in the unit a person reads it in (this.i 6d0jwr9z): ns below a microsecond,
    then µs, ms and s, to three significant figures. report.json keeps the exact nanoseconds."""
    if value is None:
        return "not seen"
    sign, size = ("-" if value < 0 else ""), abs(value)
    if size < 1_000:
        return f"{value} ns"
    for limit, unit, scale in ((1_000_000, "µs", 1e3), (1_000_000_000, "ms", 1e6)):
        if size < limit:
            return f"{sign}{_figures(size / scale)} {unit}"
    return f"{sign}{_figures(size / 1e9)} s"


_CREDENTIAL_INDEX = re.compile(r"c(\d{1,9})")


def _sampled_losses(report: dict) -> str | None:
    """For a run that took only every Nth credential past issuance, how many of its lost
    credentials are lost by construction (never shown to the verifier) and how many were taken
    through the whole lifecycle and lost (the hostile pass on #8). The run picks credential cI
    when I is a multiple of N."""
    every = (report["run"].get("lifecycle") or {}).get("full_every")
    if not (isinstance(every, int) and not isinstance(every, bool) and every > 1):
        return None
    opening = f"Only every {_ordinal(every)} credential was taken past issuance in this run"
    by_construction = failed = 0
    for credential, entry in report["reconciliation"].get("credentials", {}).items():
        index = _CREDENTIAL_INDEX.fullmatch(credential)
        if index is None:
            return (f"{opening}, so some of the credentials counted as lost were never shown to "
                    f"the verifier; the reconciliation section's counts include them.")
        if entry.get("fate") == "lost":
            if int(index.group(1)) % every:
                by_construction += 1
            else:
                failed += 1
    tail = ("none of those taken through the whole lifecycle was lost" if not failed else
            f"the other {failed} were taken through the whole lifecycle and lost")
    return (f"{opening}, so {by_construction} of the credentials counted as lost were never "
            f"shown to the verifier, and reconciliation counts them lost whether or not their "
            f"issuance succeeded (the Warnings section lists any stage that failed); {tail}.")


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _rate(per_s: float) -> str:
    return _figures(per_s)


def _summary_md(report: dict) -> list[str]:
    """The run in sentences, before any table (this.i 6d0jwr9z)."""
    run, window = report["run"], report["window"]
    measure = report["measure"]
    end = measure.split("->")[1]
    lines = ["## Summary", ""]
    lasted = window["end_ns"] - window["measured_from_ns"]
    lines.append(f"This run offered {run['rate']} credentials a second for {_ns(lasted)} "
                 f"(repetition {run['repetition']}), and {window['credentials']} credential(s) "
                 f"were requested in its measured window.")
    if report["refused"]:
        lines.append("The run is refused, for the reason given below, so its numbers are not "
                     "to be used.")
    else:  # a driver that fell behind refuses the run, so an accepted run's driver kept up
        lines.append("The harness kept to its own schedule throughout.")
    interval = report["intervals"][measure]
    if interval["measured"]:
        missing = interval["missing"]
        tail = (f"; {missing} never got there before the window closed" if missing else "")
        start = measure.split("->")[0]
        origin = "request" if start == "requested" else f"`{start}`"
        lines.append(f"From {origin} to `{end}`, the median credential took "
                     f"{_ns(interval['p50'])} and 1 in 100 took longer than "
                     f"{_ns(interval['p99'])}, over {interval['count']} credential(s){tail}.")
    else:
        lines.append(f"The measured interval, `{measure}`, could not be measured in this run.")
    reached = report["throughput"]["milestones"].get(end)
    offered = report["throughput"]["offered_per_s"]
    if reached is not None and offered:
        share = round(100 * reached["per_s"] / offered)
        lines.append(f"`{end}` was reached {_rate(reached['per_s'])} times a second against "
                     f"{_rate(offered)} offered, {share}% of the offered load.")
    for fault in report["faults"]:
        sentence = f"A {fault['kind']} on {fault['target']} was injected"
        if fault.get("time_to_ready_ns") is not None:
            sentence += (f"; it was ready again {_ns(fault['time_to_ready_ns'])} after it began, "
                         f"and the next credential succeeded "
                         f"{_ns(fault.get('time_to_first_success_ns'))} after that")
        lines.append(sentence + ".")
    if report["reconciliation"] != NOT_MEASURED:
        counts = report["reconciliation"]["summary"]
        fates = ", ".join(f"{counts[k]} {k}" for k in ("done", "resumed", "lost", "unanswered")
                          if k in counts)
        lines.append(f"Checked afterwards, of {counts.get('total', 0)} credential(s): {fates}.")
        sample = _sampled_losses(report)
        if sample is not None:
            lines.append(sample)
    warnings = len(report["warnings"])
    lines.append("There are no warnings." if not warnings else
                 f"There {'is 1 warning' if warnings == 1 else f'are {warnings} warnings'}, "
                 f"listed at the end.")
    lines += ["", ("Durations are rounded to three significant figures; the run's `report.json` "
                   "keeps them in nanoseconds. [Reading a run report]"
                   "(https://keri-foundation.github.io/keri-bench/reading-a-report/) explains each "
                   "section."), ""]
    return lines


def _interval_table(rows: Iterable[tuple[str, dict]]) -> list[str]:
    lines = ["| interval | n | missing | not measured | resolution | p50 | p90 | p99 | p99.9 "
             "| max |", "|---|---|---|---|---|---|---|---|---|---|"]
    for key, entry in rows:
        if entry["measured"]:
            values = " | ".join(_ns(entry[k]) for k in ("p50", "p90", "p99", "p99.9", "max"))
            resolution = _ns(entry["resolution_ns"])
        else:
            values, resolution = " | ".join([NOT_MEASURED] * 5), "-"
        lines.append(f"| {key} | {entry['count']} | {entry['missing']} | "
                     f"{entry['not_measured']['count']} | {resolution} | {values} |")
    return lines


def _pairs_md(report: dict) -> list[str]:
    lines = ["## The seven pairs", ""]
    for pair in PAIRS:
        verdict = report["observability"]["pairs"][pair.key]
        lines += [f"### {pair.key}", "", f"> “{pair.utah}”", ""]
        lines.append("Measurable in this run." if verdict["measurable"]
                     else f"Not measurable in this run. {verdict['gap']}")
        lines.append("")
        if pair.intervals:
            lines += _interval_table((_key(*i), report["intervals"][_key(*i)])
                                     for i in pair.intervals)
        elif pair.throughput:
            rates = report["throughput"]["pairs"][pair.key]
            lines += [f"- {name}: " + (NOT_MEASURED if rate is None else f"{rate} per second")
                      for name, rate in rates.items()]
        else:
            lines.append("See Faults for the before, during and after windows.")
        lines.append("")
    return lines


def _censored_md(incomplete: dict) -> list[str]:
    lines = [f"{incomplete['count']} credential(s) requested in the window never reached the "
             f"measure end; their latency is censored at the window's end.", ""]
    latency = incomplete["latency"]
    if latency.get("measured") is False:
        return lines + ["The censored latency is not measured: no sample could be placed on "
                        "the harness clock.", ""]
    for key in ("p50", "p90", "p99", "p99.9", "max"):
        quoted = latency[key]
        mark = " (lower bound)" if quoted["lower_bound"] else ""
        lines.append(f"- {key}: {_ns(quoted['value'])}{mark}")
    return lines + [""]


def _faults_md(faults: list[dict], start_ns: int) -> list[str]:
    lines = ["## Faults", ""]
    if not faults:
        return lines + ["No faults were scheduled in this run.", ""]
    for fault in faults:
        ended = ("not before the window closed" if fault["ended_ns"] is None
                 else f"{_ns(fault['ended_ns'] - start_ns)} into the run")
        lines += [f"### {fault['kind']} on {fault['target']}", "",
                  f"Started {_ns(fault['started_ns'] - start_ns)} into the run; ended {ended}.",
                  ""]
        if "time_to_ready_ns" in fault:
            lines += [f"- time to ready: {_ns(fault['time_to_ready_ns'])}",
                      f"- time to first success: {_ns(fault['time_to_first_success_ns'])}", ""]
        lines += _interval_table((phase, fault[phase]) for phase in ("before", "during",
                                                                     "after"))
        lines.append("")
    return lines


def render_markdown(report: dict) -> str:
    run, window, driver = report["run"], report["window"], report["driver"]
    lines = ["# keri-bench report", ""] + _summary_md(report) + ["## Provenance", "",
             f"Report schema {report['report_schema']}, generated by "
             f"{report['generator_commit']} from a timeline of schema "
             f"{report['timeline_schema']} (vocabulary {report['vocabulary_version']}) written "
             f"by harness {report['harness_commit']}. Scenario sha256 "
             f"{report['scenario_sha256']}.", "",
             f"Offered load {run['rate']} per second, repetition {run['repetition']}. The "
             f"window lasted {_ns(window['end_ns'] - window['start_ns'])}, measured after "
             f"{_ns(window['warmup_ns'])} of warmup, and covers {window['credentials']} "
             f"credential(s).", ""]
    if report["refused"]:
        lines += [f"This run is refused. {report['refused_reason']}", ""]
    for entry in report.get("unexpected_exits", []):
        lines += [_exit_sentence(entry).replace("The run is", "This run is", 1), ""]
    lines += ["## Driver check", ""]
    lines.append(("Driver check passed" if driver["ok"] else "Driver check failed")
                 + f": p99 send lag {_ns(driver['p99_lag_ns'])} against a limit of "
                 f"{_ns(driver['lag_limit_ns'])}; backlog per second {driver['backlog']}.")
    lines.append("")
    lines += _pairs_md(report)
    lines += [f"## Measured interval ({report['measure']})", ""]
    lines += _interval_table([(report["measure"], report["intervals"][report["measure"]])])
    lines.append("")
    lines += _censored_md(report["incomplete"])
    lines += ["## All intervals", ""]
    lines += _interval_table(report["intervals"].items())
    lines += ["", "## Throughput", "",
              f"Over {_ns(report['throughput']['window_ns'])} after warmup, offered "
              f"{report['throughput']['offered_per_s']} per second.", "",
              "| milestone | count | per second | unconvertible |", "|---|---|---|---|"]
    for name, rate in report["throughput"]["milestones"].items():
        lines.append(f"| {name} | {rate['count']} | {_rate(rate['per_s'])} | "
                     f"{rate['unconvertible']} |")
    lines += ["", "## Observability matrix", "",
              "| milestone | adapter | role | method | clock | resolution | events |",
              "|---|---|---|---|---|---|---|"]
    for name, seen in report["observability"]["milestones"].items():
        if seen == "unobserved":
            lines.append(f"| {name} | unobserved | | | | | |")
        else:
            lines.append(f"| {name} | {seen['adapter']} | {seen['role']} | {seen['method']} "
                         f"| {seen['clock']} | {_ns(seen['resolution_ns'])} | "
                         f"{seen['events']} |")
    lines.append("")
    lines += _faults_md(report["faults"], window["start_ns"])
    if "drift" in report:
        lines += _drift_md(report["drift"])
    lines += ["## Reconciliation", ""]
    if report["reconciliation"] == NOT_MEASURED:
        lines.append("Reconciliation was not measured in this run.")
    else:
        lines += [f"- {k}: {v}" for k, v in report["reconciliation"]["summary"].items()]
    lines += ["", "## Measurement cost", ""]
    cost = report["measurement_cost"]
    if cost == NOT_MEASURED:
        lines.append("Measurement cost was not measured in this run.")
    else:
        lines += [f"- {link}: p50 {_ns(v['p50_ns'])}, p99 {_ns(v['p99_ns'])}"
                  for link, v in cost["links"].items()]
        lines.append(f"- harness CPU: {cost['harness_cpu_s']} s")
    if "calibration" in report:
        lines += ["", "## Calibration (error budget)", ""]
        calibration = report["calibration"]
        if isinstance(calibration, dict):
            lines.append(f"Calibrated by harness {calibration['harness_commit']}; "
                         f"{'passed' if calibration['ok'] else 'FAILED'}. The worst error per "
                         f"injected transition:")
            lines += [f"- {key}: p50 {_ns(v['p50_error_ns'])}, p99 {_ns(v['p99_error_ns'])}"
                      for key, v in calibration["budget"].items()]
        else:
            lines.append("This run carries no calibration.")
    lines += ["", "## Signer census", ""] + _census_md(report["census"]) + ["## Warnings", ""]
    lines += [f"- {w}" for w in report["warnings"]] or ["No warnings."]
    return "\n".join(lines) + "\n"


def write_report(run_dir: Path, *, generator_commit: str) -> dict:
    run_dir = Path(run_dir)
    report = derive(run_dir / "timeline.jsonl", run_dir / "provenance.json",
                    generator_commit=generator_commit)
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (run_dir / "report.md").write_text(render_markdown(report))
    return report
