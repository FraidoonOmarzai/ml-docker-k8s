#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ops/rollback.sh — Safe rollback with confirmation and health verification
#
# Usage:
#   ./ops/rollback.sh                  # roll back 1 revision
#   ./ops/rollback.sh --to-revision 3  # roll back to a specific revision
#   ./ops/rollback.sh --force          # skip confirmation prompt
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

NAMESPACE="dock8s-namespace"
DEPLOYMENT="dock8s-api"
TO_REVISION=""
FORCE=false

for arg in "$@"; do
  case $arg in
    --to-revision=*) TO_REVISION="${arg#*=}" ;;
    --to-revision)   shift; TO_REVISION="$1" ;;
    --force)         FORCE=true ;;
  esac
done

GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; RED='\033[0;31m'
BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }
header()  { echo -e "\n${BOLD}━━━ $* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }


header "Rollback — ${DEPLOYMENT}"

# ── Show current state ────────────────────────────────────────────────────────
info "Current deployment state:"
kubectl get deployment $DEPLOYMENT -n $NAMESPACE \
  -o custom-columns="NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image,READY:.status.readyReplicas,REVISION:.metadata.annotations.deployment\.kubernetes\.io/revision"

echo ""
info "Rollout history:"
kubectl rollout history deployment/$DEPLOYMENT -n $NAMESPACE

echo ""

# ── Determine target revision ─────────────────────────────────────────────────
if [ -n "$TO_REVISION" ]; then
  TARGET_MSG="revision ${TO_REVISION}"
else
  TARGET_MSG="previous revision"
fi

warn "About to roll back ${DEPLOYMENT} to ${TARGET_MSG}"

# ── Confirmation ──────────────────────────────────────────────────────────────
if [ "$FORCE" = false ]; then
  read -p "Are you sure? (y/N): " confirm
  [[ "$confirm" == "y" ]] || { info "Rollback cancelled."; exit 0; }
fi

# ── Execute rollback ──────────────────────────────────────────────────────────
header "Executing Rollback"
if [ -n "$TO_REVISION" ]; then
  kubectl rollout undo deployment/$DEPLOYMENT \
    -n $NAMESPACE \
    --to-revision="$TO_REVISION"
else
  kubectl rollout undo deployment/$DEPLOYMENT -n $NAMESPACE
fi

# ── Wait for rollout ──────────────────────────────────────────────────────────
info "Waiting for rollback rollout to complete..."
kubectl rollout status deployment/$DEPLOYMENT \
  -n $NAMESPACE \
  --timeout=120s

success "Rollback complete!"

# ── Verify health ─────────────────────────────────────────────────────────────
header "Post-Rollback Health Check"
sleep 5   # give probes a moment

info "Pod status after rollback:"
kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT

echo ""
info "New deployment state:"
kubectl get deployment $DEPLOYMENT -n $NAMESPACE \
  -o custom-columns="NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image,READY:.status.readyReplicas"

echo ""
info "Updated rollout history:"
kubectl rollout history deployment/$DEPLOYMENT -n $NAMESPACE

echo ""
success "🔁 Rollback finished. Verify the API is healthy:"
echo "   kubectl port-forward svc/dock8s-api-service 8080:80 -n $NAMESPACE"
echo "   curl http://localhost:8080/health"
echo "   python ops/verify_deployment.py"