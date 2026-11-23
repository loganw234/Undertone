#!/bin/bash
# The front door: one command that answers "does it still hold?"
#
# Adapted from HonestFramework's templates/gate-runner.sh (MIT). What it keeps
# from there, by section of that method:
#   3  each real check has a negative control that must FAIL, on planted
#      faults, and must fail FOR THOSE FAULTS: the control's log has to carry
#      a CONTROL-DETECTED line. A control that passes fails the run.
#   4  the stage list is DERIVED from this file's own `stage` calls.
#   5  a real stage passes on a line only success prints ("OK <name>: <n> ..."),
#      not on its exit code. Skips print by name with a reason; --require-all
#      makes a skip a failure; an unknown stage name is refused.
#   6  a run id of timestamp + commit; --resume refuses to cross commits, and
#      refuses a tree with uncommitted changes.
#   7  an append-only JSONL record of every stage verdict.
#
# USAGE
#   bash verify/run.sh                   every stage
#   bash verify/run.sh --only links      by name (refuses unknown names)
#   bash verify/run.sh --skip claims
#   bash verify/run.sh --require-all     a skipped stage FAILS the run
#   bash verify/run.sh --list            stages, with * on what would run
#   bash verify/run.sh --resume          continue the most recent run
#   bash verify/run.sh --fresh           force a new run id
#
# THERE IS NO CACHE ACROSS RUNS. --resume skips what passed IN THIS RUN ID.
# PYTHON=<interpreter> overrides the interpreter the checks run under.
set -uo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
STATEROOT="${STATEROOT:-$ROOT/verify/state}"

ONLY=""; SKIP=""; REQUIRE_ALL=0; LIST=0; RESUME=""; FRESH=0

die () { echo "FATAL: $*" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --only)        [ $# -ge 2 ] || die "--only needs a list"; ONLY="$ONLY,$2"; shift 2;;
    --skip)        [ $# -ge 2 ] || die "--skip needs a list"; SKIP="$SKIP,$2"; shift 2;;
    --require-all) REQUIRE_ALL=1; shift;;
    --list)        LIST=1; shift;;
    --resume)      if [ $# -gt 1 ] && [[ ${2:-} != --* ]]; then RESUME=$2; shift 2
                   else RESUME=last; shift; fi;;
    --fresh)       FRESH=1; shift;;
    -h|--help)     sed -n '2,27p' "$0"; exit 0;;
    *)             die "unknown option $1";;
  esac
done

in_list() {  # name, comma-list
  case ",$2," in *",$1,"*) return 0;; esac
  return 1
}

# The only copy of the stage list is the `stage` calls themselves.
SELF="${BASH_SOURCE[0]}"
STAGELIST=$(grep -E '^stage [a-z0-9-]+ "' "$SELF" | awk '{print $2}' | tr '\n' ' ')
STAGELIST="${STAGELIST% }"

if [ "$LIST" = 1 ]; then
  while IFS=$'\t' read -r _nm _ds; do
    if [ -z "$ONLY" ] || in_list "$_nm" "$ONLY"; then _mk="*"; else _mk=" "; fi
    printf '%s %-17s%s\n' "$_mk" "$_nm" "$_ds"
  done < <(grep -E '^stage [a-z0-9-]+ "' "$SELF" \
      | sed -E 's/^stage ([a-z0-9-]+) +"([^"]*)".*/\1\t\2/')
  echo
  if [ -n "$ONLY" ]; then echo "* = would run. Unmarked stages are NOT in this selection."
  else echo "* = would run: every stage (no --only)."; fi
  exit 0
fi

check_names() {  # <flagname> <comma-list>
  local n
  for n in $(echo "$2" | tr ',' ' '); do
    [ -z "$n" ] && continue
    case " $STAGELIST " in
      *" $n "*) ;;
      *) echo "ERROR: $1 names unknown stage '$n'" >&2
         echo "       stages: $STAGELIST" >&2
         exit 2;;
    esac
  done
}
check_names --only "$ONLY"
check_names --skip "$SKIP"

COMMIT=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo nocommit)
DIRTY=$(git -C "$ROOT" status --porcelain 2>/dev/null | grep -c .)
if [ -n "$RESUME" ] && [ "$FRESH" = 1 ]; then
  die "--resume and --fresh are contradictory"
fi
if [ -n "$RESUME" ]; then
  # A run id names a commit. On a tree with no commit, or with uncommitted
  # changes, nothing says what the earlier stages ran on, so resuming would
  # glue a pass on one tree to a run on another.
  if [ "$COMMIT" = nocommit ] || [ "$DIRTY" -ne 0 ]; then
    die "REFUSED: --resume on a tree with no commit or with uncommitted changes ($DIRTY path(s)). Run without --resume."
  fi
  if [ "$RESUME" = last ]; then
    RUNID=$(ls -1 "$STATEROOT" 2>/dev/null | sort | tail -n 1)
    [ -n "$RUNID" ] || die "--resume: no previous run under $STATEROOT"
  else
    RUNID=$RESUME
  fi
  case "$RUNID" in
    *-"$COMMIT") ;;
    *) die "run $RUNID was a different commit than $COMMIT. Use --fresh.";;
  esac
else
  RUNID="$(date +%Y%m%d-%H%M%S)-$COMMIT"
fi
RUNDIR="$STATEROOT/$RUNID"
mkdir -p "$RUNDIR"
JSONL="$RUNDIR/stages.jsonl"

# The interpreter. Named, with its version, because "which python ran this"
# is otherwise unanswerable afterwards.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3
  elif command -v python >/dev/null 2>&1; then PY=python; fi
fi

PASSED=0; FAILED=0; SKIPPED=0; CACHED=0; SELECTED=0; INNER=0
note () { echo "   $*"; }

echo "== run $RUNID"
echo "   commit $COMMIT, tree $DIRTY uncommitted path(s), state in $RUNDIR"
if [ -n "$PY" ]; then echo "   python: $PY ($("$PY" --version 2>&1 | head -n 1))"
else echo "   python: NONE FOUND"; fi

# stage <name> <description> -- command...
# MUST_FAIL=1 before a stage inverts it: the command must fail, AND its log
# must carry a CONTROL-DETECTED line, or the run fails.
stage() {
  local name=$1 desc=$2; shift 3
  local t0 t1 rc verdict="" reason="" expect_fail="${MUST_FAIL:-0}"
  MUST_FAIL=0

  if [ -n "$ONLY" ] && ! in_list "$name" "$ONLY"; then
    return 0
  fi
  SELECTED=$((SELECTED+1))
  if [ -f "$RUNDIR/$name.ok" ]; then
    CACHED=$((CACHED+1))
    note "$(printf '%-17s %-5s %s' "$name" "ok" "(passed earlier in this run)")"
    echo "{\"stage\":\"$name\",\"verdict\":\"ok-cached\"}" >> "$JSONL"
    return 0
  fi
  if in_list "$name" "$SKIP"; then
    verdict=SKIP; reason="requested"
  elif [ -z "$PY" ]; then
    verdict=SKIP; reason="no python interpreter found (set PYTHON=)"
  fi
  if [ "$verdict" = SKIP ]; then
    SKIPPED=$((SKIPPED+1))
    note "$(printf '%-17s %-5s %s' "$name" "SKIP" "$reason")"
    echo "{\"stage\":\"$name\",\"verdict\":\"skip\",\"reason\":\"$reason\"}" >> "$JSONL"
    [ "$REQUIRE_ALL" = 1 ] && FAILED=$((FAILED+1))
    return 0
  fi

  t0=$(date +%s)
  "$@" > "$RUNDIR/$name.log" 2>&1
  rc=$?
  t1=$(date +%s)

  if [ "$expect_fail" = 1 ]; then
    if [ "$rc" -ne 0 ] && grep -q '^CONTROL-DETECTED ' "$RUNDIR/$name.log"; then
      : > "$RUNDIR/$name.ok"
      PASSED=$((PASSED+1))
      note "$(printf '%-17s %-5s %s' "$name" "ok" "(control failed as it must: $(grep -m1 '^CONTROL-DETECTED ' "$RUNDIR/$name.log"))")"
      echo "{\"stage\":\"$name\",\"verdict\":\"ok\",\"control\":true,\"seconds\":$((t1-t0))}" >> "$JSONL"
      return 0
    fi
    : > "$RUNDIR/$name.fail"
    FAILED=$((FAILED+1))
    note "$(printf '%-17s %-5s %s' "$name" "FAIL" "NEGATIVE CONTROL DID NOT FAIL (rc=$rc) - this check cannot detect its fault; see $RUNDIR/$name.log")"
    echo "{\"stage\":\"$name\",\"verdict\":\"control-passed\",\"rc\":$rc}" >> "$JSONL"
    return 0
  fi

  # A real stage passes on the line only success prints, never on rc alone.
  if [ "$rc" -eq 0 ] && grep -q "^OK $name: [1-9]" "$RUNDIR/$name.log"; then
    : > "$RUNDIR/$name.ok"
    PASSED=$((PASSED+1))
    # A check skipped INSIDE a stage that passed is counted and named too.
    local inner; inner=$(grep -c '^SKIPPED ' "$RUNDIR/$name.log")
    if [ "$inner" -ne 0 ]; then
      INNER=$((INNER+inner))
      grep '^SKIPPED ' "$RUNDIR/$name.log" | head -n 20 | sed "s/^/      $name: /"
    fi
    note "$(printf '%-17s %-5s %ss  %s' "$name" "ok" "$((t1-t0))" "$(grep -m1 "^OK $name: " "$RUNDIR/$name.log")")"
    echo "{\"stage\":\"$name\",\"verdict\":\"ok\",\"seconds\":$((t1-t0))}" >> "$JSONL"
  else
    : > "$RUNDIR/$name.fail"
    FAILED=$((FAILED+1))
    note "$(printf '%-17s %-5s rc=%s  see %s' "$name" "FAIL" "$rc" "$RUNDIR/$name.log")"
    grep -E '^(FINDING|REFUSED|FAIL) ' "$RUNDIR/$name.log" | head -n 20 | sed 's/^/      /'
    echo "{\"stage\":\"$name\",\"verdict\":\"fail\",\"rc\":$rc}" >> "$JSONL"
  fi
}

check ()   { "$PY" "$ROOT/tools/check_tree.py" "$1" --root "$ROOT"; }
control () { "$PY" "$ROOT/tools/check_tree.py" control "$1" --scratch "$RUNDIR/control-$1"; }
# The build checks: what the tree generates, runs and imports.
build ()   { "$PY" "$ROOT/tools/check_build.py" "$1" --root "$ROOT" --state "$RUNDIR/$1"; }
bcontrol () { "$PY" "$ROOT/tools/check_build.py" control "$1" --root "$ROOT" --scratch "$RUNDIR/control-$1"; }

# ======================================================================
# THE STAGES. One `stage` line each, the description in double quotes on
# the same line so the derivation above finds it.
# ======================================================================

stage links "every relative markdown link in a committable file resolves" -- check links
stage paths "no personal path in any committable file" -- check paths
stage claims "every claims-register row under docs/ carries a basis label" -- check claims
stage eol "no CR byte in any committable text file" -- check eol
stage generated "the generated constants and the vectors' checksum lists equal their sources" -- build generated
stage model-tests "the tests under tests/ pass, read from their results file" -- build model-tests
stage independence "model/ and stats/ each import with the other blocked" -- build independence
stage registry "gate rows and gate-claiming tests agree, in both directions" -- build registry

# The controls. Each plants a list of faults in a throwaway repository under
# this run's own state folder and runs the same check on it. Every planted
# fault must be reported, and nothing else.
MUST_FAIL=1
stage ctl-links "every planted broken link MUST be reported" -- control links
MUST_FAIL=1
stage ctl-paths "every planted personal path MUST be reported" -- control paths
MUST_FAIL=1
stage ctl-claims "every planted unlabelled claim MUST be reported" -- control claims
MUST_FAIL=1
stage ctl-eol "every planted CR byte MUST be reported" -- control eol
MUST_FAIL=1
stage ctl-generated "an edited constant and an edited vector MUST each be reported" -- bcontrol generated
MUST_FAIL=1
stage ctl-model-tests "a planted failing test MUST fail, and a tree with no test MUST be refused" -- bcontrol model-tests
MUST_FAIL=1
stage ctl-independence "a planted import across model/ and stats/ MUST be reported, each way" -- bcontrol independence
MUST_FAIL=1
stage ctl-registry "a row nothing claims and a test with no row MUST each be reported" -- bcontrol registry

# ======================================================================

echo "== summary"
NSTAGES=$(echo "$STAGELIST" | wc -w | tr -d " ")
# Counted from the stages selected, not from the verdict counters: under
# --require-all a skip is both a skip and a failure, and summing those gave -1.
NOTRUN=$((NSTAGES - SELECTED))
echo "   passed $PASSED, failed $FAILED, skipped $SKIPPED, cached $CACHED, not selected $NOTRUN of $NSTAGES"
echo "   record $JSONL"
if [ "$INNER" -ne 0 ]; then
  echo "   $INNER check(s) were skipped inside stages that passed; they are named above"
  [ "$REQUIRE_ALL" = 1 ] && FAILED=$((FAILED+1))
fi
if [ "$FAILED" -ne 0 ]; then
  echo "== VERDICT: FAIL"
  exit 1
fi
if [ $((PASSED + CACHED)) -eq 0 ]; then
  echo "== VERDICT: FAIL (no stage passed; nothing was established)"
  exit 1
fi
SCOPE=""
[ "$NOTRUN" -ne 0 ] && SCOPE=" for the selected stages only: $NOTRUN of $NSTAGES stage(s) were NOT run"
if [ "$SKIPPED" -ne 0 ] || [ "$INNER" -ne 0 ]; then
  echo "== VERDICT: PASS$SCOPE, with $SKIPPED stage(s) and $INNER inner check(s) skipped by name above (--require-all makes a skip a failure)"
  exit 0
fi
echo "== VERDICT: PASS$SCOPE"
exit 0
