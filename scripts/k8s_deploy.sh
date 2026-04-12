#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# k8s_deploy.sh — Apply all manifests and verify the deployment is healthy
#
# Usage:
#   ./k8s_deploy.sh                    # full deploy
#   ./k8s_deploy.sh --skip-build       # skip docker build (use existing image)
#   ./k8s_deploy.sh --dry-run          # kubectl dry-run only (no changes)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

NAMESPACE="dock8s-namespace"
DEPLOYMENT="dock8s-api"
IMAGE="faidoonjan/dock8s:latest"
K8S_DIR="./k8s"
SKIP_BUILD=false
DRY_RUN=false

# Parse flags
for arg in "$@"; do
  case $arg in
    --skip-build) SKIP_BUILD=true ;;
    --dry-run)    DRY_RUN=true ;;
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

KUBECTL_FLAGS=""
[ "$DRY_RUN" = true ] && KUBECTL_FLAGS="--dry-run=client"

# ── Step 0: Pre-flight checks ─────────────────────────────────────────────────
header "Step 0: Pre-flight Checks"
command -v kubectl >/dev/null || error "kubectl not found. Install kubectl first."
command -v docker  >/dev/null || error "docker not found."

K8S_VERSION=$(kubectl version --client --short 2>/dev/null | head -1)
info "kubectl: ${K8S_VERSION}"

CONTEXT=$(kubectl config current-context 2>/dev/null || echo "none")
info "Current context: ${CONTEXT}"

# Safety check: warn if pointed at a production cluster
if [[ "$CONTEXT" == *"prod"* ]]; then
  warn "⚠️  You are targeting a PRODUCTION context: ${CONTEXT}"
  read -p "Continue? (y/N): " confirm
  [[ "$confirm" == "y" ]] || exit 0
fi


# ── Step 1: Build & load Docker image ────────────────────────────────────────
header "Step 1: Docker Image"
if [ "$SKIP_BUILD" = false ]; then
  info "Building image: ${IMAGE}"
  docker build -t ${IMAGE} .
  success "Image built"
else
  warn "Skipping build (--skip-build)"
fi

# For minikube: load local image into minikube's Docker daemon
if kubectl config current-context 2>/dev/null | grep -q "minikube"; then
  info "Loading image into minikube..."
  minikube image load ${IMAGE}
  success "Image loaded into minikube"
fi


# ── Step 2: Apply manifests in order ─────────────────────────────────────────
header "Step 2: Apply Kubernetes Manifests"

MANIFESTS=(
  "namespace.yaml"
  "configmap.yaml"
  "deployment.yaml"
  "service.yaml"
  "hpa.yaml"
  "ingress.yaml"
)

for manifest in "${MANIFESTS[@]}"; do
  path="${K8S_DIR}/${manifest}"
  if [ -f "$path" ]; then
    info "Applying ${manifest}..."
    kubectl apply -f "$path" $KUBECTL_FLAGS
    success "${manifest} applied"
  else
    warn "Skipping missing file: ${path}"
  fi
done


# ── Step 3: Wait for rollout ──────────────────────────────────────────────────
if [ "$DRY_RUN" = false ]; then
  header "Step 3: Wait for Rollout"
  info "Waiting for deployment rollout (timeout: 120s)..."
  kubectl rollout status deployment/${DEPLOYMENT} \
    -n ${NAMESPACE} \
    --timeout=120s
  success "Rollout complete!"
fi


# ── Step 4: Verify pods ────────────────────────────────────────────────────────
header "Step 4: Verify Pods"
info "Pod status:"
kubectl get pods -n ${NAMESPACE} -l app=${DEPLOYMENT} \
  -o custom-columns="NAME:.metadata.name,STATUS:.status.phase,READY:.status.conditions[?(@.type=='Ready')].status,RESTARTS:.status.containerStatuses[0].restartCount,AGE:.metadata.creationTimestamp"

echo ""
info "Deployment summary:"
kubectl get deployment ${DEPLOYMENT} -n ${NAMESPACE}

echo ""
info "Services:"
kubectl get svc -n ${NAMESPACE}

echo ""
info "HPA status:"
kubectl get hpa -n ${NAMESPACE} 2>/dev/null || warn "HPA not ready yet (metrics-server may need a moment)"

echo ""
info "Ingress:"
kubectl get ingress -n ${NAMESPACE} 2>/dev/null || warn "No ingress found"


# ── Step 5: Port-forward for local access ────────────────────────────────────
header "Step 5: Access the API"
echo ""
echo -e "  ${CYAN}Option A — Port-forward (quickest):${NC}"
echo -e "    kubectl port-forward svc/iris-ml-api 8080:80 -n ${NAMESPACE}"
echo -e "    curl http://localhost:8080/health"
echo ""
echo -e "  ${CYAN}Option B — minikube service URL:${NC}"
echo -e "    minikube service iris-ml-api-external -n ${NAMESPACE} --url"
echo ""
echo -e "  ${CYAN}Option C — Ingress (after DNS setup):${NC}"
echo -e "    curl http://iris-api.local/health"
echo ""
success "🎉 Deployment complete! Namespace: ${NAMESPACE}"