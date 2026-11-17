#!/usr/bin/env bash
# NFR07: deploy PEKA from a clean clone with the documented steps and time each step.
# Isolated Compose project (peka-deploytest); does not touch the dev stack.
set -uo pipefail
REPO=${REPO:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}
DEST=${DEST:-$REPO/../peka-deploytest}
OUT=$(dirname "$0")
export COMPOSE_PROJECT_NAME=peka-deploytest
log() { echo "$(date '+%F %T') $*" | tee -a "$OUT/deploy.log"; }
step() { local name=$1; shift; local t=$(date +%s); log "START $name"; "$@" >>"$OUT/deploy-detail.log" 2>&1; local rc=$?; log "END $name rc=$rc $(( $(date +%s) - t ))s"; return $rc; }
wait_url() { for _ in $(seq 1 360); do curl -fsS -o /dev/null "$1" && return 0; sleep 5; done; return 1; }

: >"$OUT/deploy.log"; : >"$OUT/deploy-detail.log"
T0=$(date +%s)
log "host: $(uname -r), $(nproc) CPU threads, $(free -g | awk '/Mem/{print $2}') GiB RAM; docker $(docker version -f '{{.Server.Version}}'); commit $(git -C $REPO rev-parse --short main)"

step clone git clone --branch main "$REPO" "$DEST" || exit 1
cd "$DEST"
step env-files sh -c '
  cp service/.env.example service/.env &&
  sed -i -e "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -hex 32)/" \
         -e "s/^ADMIN_EMAIL=.*/ADMIN_EMAIL=admin@example.com/" \
         -e "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$(openssl rand -hex 12)/" service/.env' || exit 1
# Deviation 1: on the test host, port 8000 was used by another project, so the dev API port moved (documented bind-address edit).
sed -i 's/"127.0.0.1:8000:8000"/"127.0.0.1:18000:8000"/' config/compose.dev.yaml
# Deviation 2: the 3.2 GB model file is linked, not downloaded (it is gitignored and must be fetched once).
mkdir -p config/model  # added after the 2026-11-17 run, which lacked it (see README)
ln "$REPO/config/model/"*.gguf config/model/

cd config
step make-setup make setup || { log "make setup failed"; exit 1; }
step make-llm make llm || exit 1
step wait-api wait_url http://127.0.0.1:3000/api/health
step wait-llama wait_url http://127.0.0.1:8080/health
step wait-ui wait_url http://127.0.0.1:3000/sign-in
EMAIL=$(sed -n 's/^ADMIN_EMAIL=//p' ../service/.env); PASS=$(sed -n 's/^ADMIN_PASSWORD=//p' ../service/.env)
step login curl -fsS -X POST http://127.0.0.1:3000/api/auth/login -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" -o /dev/null
log "TOTAL $(( $(date +%s) - T0 ))s"
docker compose -f compose.yaml -f compose.dev.yaml --profile llama ps --format '{{.Service}} {{.Status}}' | tee -a "$OUT/deploy.log"
