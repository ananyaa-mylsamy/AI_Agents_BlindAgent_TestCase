#!/bin/bash
# Run the FlyFinder test case once, from a fresh environment.
#
#   ./run.sh dry-run                              checks the setup; no API calls
#   ./run.sh simulated <run-id> [layer-off|layer-on]   Hope (an LLM) plays the user
#   ./run.sh human     <run-id> [layer-off|layer-on]   a person plays the user
#
# Each run: docker compose down, a new runs/run-<id> folder mounted at /output,
# a fresh site (state is in memory, so this is the reset), the agent, then
# make_outputs.py, docker compose down, and reward.json is printed.
set -u
export COMPOSE_PROGRESS=quiet
cd "$(dirname "$0")"

MODE="${1:-}"; ID="${2:-}"; LAYER="${3:-layer-off}"
usage() { sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[ -z "$MODE" ] && usage
case "$LAYER" in layer-off) L=off ;; layer-on) L=on ;; *) echo "Layer must be layer-off or layer-on."; exit 2 ;; esac

env_value() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | tr -d '"'"'"' \r' ; }

fresh_site() {
  docker compose down --remove-orphans >/dev/null 2>&1
  docker compose up -d --wait sites >/dev/null || { echo "The site did not start. See: docker compose logs sites"; exit 1; }
}

new_run_dir() {
  RUN="runs/run-$1"
  if [ -e "$RUN" ] && [ -n "$(ls -A "$RUN" 2>/dev/null)" ]; then
    echo "$RUN already exists. Pick a new run id, or delete that folder first."; exit 1
  fi
  mkdir -p "$RUN"
  export RUN_DIR="./$RUN"
}

score() {
  docker compose run --rm -T --no-deps agent make_outputs.py /output
}

case "$MODE" in
  dry-run)
    docker compose build -q || exit 1
    export RUN_DIR="./runs/.dry-run"; mkdir -p "$RUN_DIR"
    fresh_site
    docker compose run --rm -T agent run_case.py --dry-run --out /output; status=$?
    docker compose down --remove-orphans >/dev/null 2>&1
    rm -rf "$RUN_DIR"
    exit $status
    ;;

  simulated|human)
    [ -z "$ID" ] && usage
    if [ "$(env_value ALLOW_API_CALLS)" != "1" ]; then
      echo "API calls are disabled. Set ALLOW_API_CALLS=1 in .env to run."; exit 3
    fi
    docker compose build -q || exit 1
    new_run_dir "$ID"
    fresh_site
    if [ "$MODE" = "human" ]; then
      echo "Human mode. Agent messages appear below and in $RUN/agent_messages.txt."
      echo "Optional, in another terminal: ./speak_agent.sh $RUN"
      docker compose run --rm agent run_case.py --mode human --layer "$L" --out /output
    else
      docker compose run --rm -T agent run_case.py --mode simulated --layer "$L" --out /output
    fi
    score
    docker compose down --remove-orphans >/dev/null 2>&1
    echo "$RUN/reward.json:"; cat "$RUN/reward.json"; echo
    ;;

  *) usage ;;
esac
