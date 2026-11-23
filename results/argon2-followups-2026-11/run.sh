#!/bin/bash
# The argon2 follow-ups (this.i 3s6zgux4), started after midnight by a systemd timer, at imbu
# 7b544ac and heti 093acb3, from the detached worktree .worktrees/night-runs (harness 22f483e):
#   1. probe-capacity-1home at 5.0, 6.0 and 8.0 a second (one issuer's new ceiling)
#   2. probe-capacity-3homes at its rates (2.8, 4.0, 5.0) and 6.0, 8.0, 12.0
#   3. peak-hour-1home, the ten-minute peak hour at one issuer
#   4. peak-hour-1home-hour, the full peak hour at one issuer
# Unlike the argon2 rerun's run.sh (tick ~6lry), it refuses on a failed flock, refuses an
# unreadable load, gives up if the host is not quiet by 05:00 local, collects every run it made,
# and ends by naming every run that failed.
set -uo pipefail
tree=/home/daniel/code/bakobo/keri-bench/.worktrees/night-runs
out=/home/daniel/code/bakobo/keri-bench/.ignored/night-2026-11-21
work=$out/work
results=$out/results
mkdir -p "$work" "$results"
say() { echo "$(date -u +%FT%TZ) $*"; }

exec 9>"$HOME/.local/state/bench-host.lock" || { say "cannot open the lock file"; exit 3; }
say "waiting for the bench-host lock"
flock 9 || { say "flock failed; not running unlocked"; exit 3; }
say "lock held"

deadline=$(date -d 'today 05:00' +%s)
while :; do
    l=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null)
    [[ "$l" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { say "unreadable load '$l'; stopping"; exit 3; }
    awk -v l="$l" 'BEGIN{exit !(l < 2.0)}' && break
    [ "$(date +%s)" -lt "$deadline" ] || { say "not quiet by 05:00 (load $l); giving up"; exit 5; }
    say "load $l"
    sleep 60
done
say "quiet at load $(cut -d' ' -f1 /proc/loadavg)"

(while true; do echo "$(date -u +%FT%TZ) $(cut -d' ' -f1-3 /proc/loadavg)"; sleep 60; done) \
    >> "$work/loadavg.log" &
logger=$!
trap 'kill $logger 2>/dev/null || true' EXIT

cd "$tree" || exit 3
# A failed calibration means the host is too busy (this.i 0hykugwr): stop, never retry.
uv run --project "$tree" keri-bench calibrate --out "$work/calibration" \
    || { say "calibration failed; stopping"; exit 4; }
cal=$work/calibration/calibration.json

failed=()
one() {  # scenario rate
    local name; name=$(basename "$1" .toml)
    say "start $name at $2"
    uv run --project "$tree" keri-bench run "$1" --out "$work/$name" --rate "$2" \
        --calibration "$cal" || failed+=("$name@$2")
    say "end $name at $2"
}
for r in 5.0 6.0 8.0; do one scenarios/targets/probe-capacity-1home.toml "$r"; done
for r in 2.8 4.0 5.0 6.0 8.0 12.0; do one scenarios/targets/probe-capacity-3homes.toml "$r"; done
one scenarios/targets/peak-hour-1home.toml 2.8
one scenarios/targets/peak-hour-1home-hour.toml 2.8

mkdir -p "$results/calibration"
cp "$cal" "$results/calibration/"
kill $logger 2>/dev/null || true
cp "$work/loadavg.log" "$results/"
(cd "$work" && find . -path ./calibration -prune -o \( -name timeline.jsonl -o \
    -name provenance.json -o -name report.json -o -name report.md -o -name sweep.json \
    -o -name imbu-answers.json \) -print) | while read -r f; do
    mkdir -p "$results/$(dirname "$f")"; cp "$work/$f" "$results/$f"
done
say "collected into $results"
if [ ${#failed[@]} -gt 0 ]; then say "FAILED: ${failed[*]}"; exit 6; fi
say "all done, none failed"
