#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_local.sh  —  Full local Docker workflow: build → train → run → test
# Usage: chmod +x run_local.sh && ./run_local.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

IMAGE_NAME="dock8s"
IMAGE_TAG="latest"
CONTAINER_NAME="dock8s-container"
PORT=8080

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; }
header()  { echo -e "\n${BOLD}━━━ $* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }


# ── Step 1: Train model (generate artifacts) ──────────────────────────────────
header "Step 1: Train Model"
info "Installing training deps..."
pip install -q -r requirements-train.txt

info "Running trainer..."
python model/train.py
success "Artifacts saved to model/artifacts/"


# ── Step 2: Build Docker image ────────────────────────────────────────────────
header "Step 2: Build Docker Image"
info "Building ${IMAGE_NAME}:${IMAGE_TAG} ..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
success "Image built: $(docker image ls ${IMAGE_NAME} --format '{{.Repository}}:{{.Tag}} | Size: {{.Size}}')"


# ── Step 3: Stop any existing container ───────────────────────────────────────
header "Step 3: Clean Up Old Container"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    warn "Stopping existing container: ${CONTAINER_NAME}"
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm   ${CONTAINER_NAME} 2>/dev/null || true
fi
success "Clean"


# ── Step 4: Run container ─────────────────────────────────────────────────────
header "Step 4: Run Container"
info "Starting container on port ${PORT}..."
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:8080 \
    -e ARTIFACTS_DIR=/app/model/artifacts \
    --restart unless-stopped \
    ${IMAGE_NAME}:${IMAGE_TAG}

success "Container started: ${CONTAINER_NAME}"
info "Waiting for container to be healthy..."

# Poll /health until ready (max 30s)
for i in $(seq 1 15); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT}/health 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        success "Container is healthy! (attempt ${i})"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""


# ── Step 5: Quick curl smoke tests ───────────────────────────────────────────
header "Step 5: Smoke Tests (curl)"

info "GET /health"
curl -s http://localhost:${PORT}/health | python3 -m json.tool

echo ""
info "POST /predict — Setosa"
curl -s -X POST http://localhost:${PORT}/predict \
    -H "Content-Type: application/json" \
    -d '{"features": [5.1, 3.5, 1.4, 0.2]}' | python3 -m json.tool

echo ""
info "POST /predict — Virginica"
curl -s -X POST http://localhost:${PORT}/predict \
    -H "Content-Type: application/json" \
    -d '{"features": [6.7, 3.0, 5.2, 2.3]}' | python3 -m json.tool

echo ""
info "POST /predict/batch — 3 samples"
curl -s -X POST http://localhost:${PORT}/predict/batch \
    -H "Content-Type: application/json" \
    -d '{
        "features": [
            [5.1, 3.5, 1.4, 0.2],
            [6.7, 3.0, 5.2, 2.3],
            [5.8, 2.7, 4.1, 1.0]
        ]
    }' | python3 -m json.tool

echo ""
info "POST /predict — Bad input (expect 422)"
curl -s -X POST http://localhost:${PORT}/predict \
    -H "Content-Type: application/json" \
    -d '{"features": [5.1, 3.5]}' | python3 -m json.tool


# ── Step 6: Full Python test suite ───────────────────────────────────────────
header "Step 6: Full Test Suite"
python3 test_local.py --base-url http://localhost:${PORT}


# ── Step 7: Container info ────────────────────────────────────────────────────
header "Step 7: Container Info"
info "Running containers:"
docker ps --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

echo ""
info "Container logs (last 20 lines):"
docker logs ${CONTAINER_NAME} --tail 20

echo ""
success "🎉 All done! Container is running at http://localhost:${PORT}"
echo -e "   ${CYAN}Swagger UI:${NC} http://localhost:${PORT}/docs"
echo -e "   ${CYAN}Stop with:${NC}  docker stop ${CONTAINER_NAME}"
echo -e "   ${CYAN}Logs:${NC}       docker logs -f ${CONTAINER_NAME}"