# =============================================================================
# ops/rollback.ps1 — Safe rollback with confirmation and health verification
#
# Usage:
#   .\ops\rollback.ps1                       # roll back 1 revision
#   .\ops\rollback.ps1 -ToRevision 3         # roll back to a specific revision
#   .\ops\rollback.ps1 -Force                # skip confirmation prompt
# =============================================================================

# =============================================================================
# ops/rollback.ps1 — Safe Kubernetes rollback (production-safe version)
# =============================================================================

param(
    [string]$ToRevision = "",
    [switch]$Force
)

$NAMESPACE  = "dock8s-namespace"
$DEPLOYMENT = "dock8s-api"

function Info    { param($m) Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Success { param($m) Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn    { param($m) Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err     { param($m) Write-Host "[ERR]  $m"; exit 1 }
function Header {
    param($m)

    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Magenta
    Write-Host "  $m" -ForegroundColor White
    Write-Host ("=" * 60) -ForegroundColor Magenta
}

$ErrorActionPreference = "Stop"

Header "Rollback — $DEPLOYMENT"

# ── Validate deployment exists ───────────────────────────────────────────────
kubectl get deployment $DEPLOYMENT -n $NAMESPACE *> $null
if ($LASTEXITCODE -ne 0) {
    Err "Deployment '$DEPLOYMENT' not found in namespace '$NAMESPACE'"
}

# ── Show current state ───────────────────────────────────────────────────────
Info "Current rollout status:"
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE

Write-Host ""
Info "Rollout history:"
kubectl rollout history deployment/$DEPLOYMENT -n $NAMESPACE

Write-Host ""

# ── Validate revision if provided ─────────────────────────────────────────────
if ($ToRevision -ne "") {
    Info "Checking if revision $ToRevision exists..."
    $history = kubectl rollout history deployment/$DEPLOYMENT -n $NAMESPACE --no-headers
    if ($history -notmatch "^\s*$ToRevision\s") {
        Err "Revision $ToRevision does not exist. Check rollout history."
    }
}

# ── Confirmation ──────────────────────────────────────────────────────────────
$targetMsg = if ($ToRevision) { "revision $ToRevision" } else { "previous revision" }
Warn "About to rollback $DEPLOYMENT to $targetMsg"

if (-not $Force) {
    $confirm = Read-Host "Proceed? (y/N)"
    if ($confirm -ne "y") {
        Info "Rollback cancelled."
        exit 0
    }
}

# ── Execute rollback ─────────────────────────────────────────────────────────
Header "Executing Rollback"

if ($ToRevision) {
    kubectl rollout undo deployment/$DEPLOYMENT -n $NAMESPACE --to-revision=$ToRevision
} else {
    kubectl rollout undo deployment/$DEPLOYMENT -n $NAMESPACE
}

if ($LASTEXITCODE -ne 0) {
    Err "Rollback command failed"
}

# ── Wait for completion ──────────────────────────────────────────────────────
Info "Waiting for rollout to stabilize..."
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=120s

if ($LASTEXITCODE -ne 0) {
    Err "Rollback did not complete successfully"
}

Success "Rollback complete!"

# ── Post-checks ──────────────────────────────────────────────────────────────
Header "Post-Rollback Health Check"

Start-Sleep -Seconds 5

Info "Pod status:"
kubectl get pods -n $NAMESPACE

Write-Host ""
Info "Deployment status:"
kubectl get deployment $DEPLOYMENT -n $NAMESPACE

Write-Host ""
Info "ReplicaSet history:"
kubectl get rs -n $NAMESPACE -l app=$DEPLOYMENT

# ── Access hints ──────────────────────────────────────────────────────────────
Write-Host ""
Success "Verify API health:"
Write-Host "  kubectl port-forward svc/iris-ml-api 8080:80 -n $NAMESPACE" -ForegroundColor Cyan
Write-Host "  curl http://localhost:8080/health" -ForegroundColor Cyan
Write-Host "  python ops/verify_deployment.py" -ForegroundColor Cyan