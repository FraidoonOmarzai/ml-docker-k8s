# =============================================================================
# ops/rollback.ps1 — Safe rollback with confirmation and health verification
#
# Usage:
#   .\ops\rollback.ps1                       # roll back 1 revision
#   .\ops\rollback.ps1 -ToRevision 3         # roll back to a specific revision
#   .\ops\rollback.ps1 -Force                # skip confirmation prompt
# =============================================================================

param(
    [string]$ToRevision = "",
    [switch]$Force
)

$NAMESPACE  = "ml-system"
$DEPLOYMENT = "iris-ml-api"

function Info    { param($m) Write-Host "[INFO] $m" -ForegroundColor Cyan    }
function Success { param($m) Write-Host "[OK]   $m" -ForegroundColor Green   }
function Warn    { param($m) Write-Host "[WARN] $m" -ForegroundColor Yellow  }
function Err     { param($m) Write-Host "[ERR]  $m" -ForegroundColor Red; exit 1 }
function Header  { param($m)
    Write-Host ""
    Write-Host ("━" * 55) -ForegroundColor Magenta
    Write-Host "  $m"     -ForegroundColor White
    Write-Host ("━" * 55) -ForegroundColor Magenta
}

$ErrorActionPreference = "Stop"

Header "Rollback — $DEPLOYMENT"

# ── Show current state ────────────────────────────────────────────────────────
Info "Current deployment state:"
kubectl get deployment $DEPLOYMENT -n $NAMESPACE `
    -o custom-columns="NAME:.metadata.name,READY:.status.readyReplicas,REVISION:.metadata.annotations.deployment\.kubernetes\.io/revision"

Write-Host ""
Info "Rollout history:"
kubectl rollout history "deployment/$DEPLOYMENT" -n $NAMESPACE
Write-Host ""

# ── Determine target ──────────────────────────────────────────────────────────
$targetMsg = if ($ToRevision) { "revision $ToRevision" } else { "previous revision" }
Warn "About to roll back $DEPLOYMENT to $targetMsg"

# ── Confirmation ──────────────────────────────────────────────────────────────
if (-not $Force) {
    $confirm = Read-Host "Are you sure? (y/N)"
    if ($confirm -ne "y") {
        Info "Rollback cancelled."
        exit 0
    }
}

# ── Execute rollback ──────────────────────────────────────────────────────────
Header "Executing Rollback"
if ($ToRevision) {
    kubectl rollout undo "deployment/$DEPLOYMENT" -n $NAMESPACE --to-revision=$ToRevision
} else {
    kubectl rollout undo "deployment/$DEPLOYMENT" -n $NAMESPACE
}
if ($LASTEXITCODE -ne 0) { Err "Rollback command failed." }

# ── Wait for rollout ──────────────────────────────────────────────────────────
Info "Waiting for rollback to complete (timeout: 120s)..."
kubectl rollout status "deployment/$DEPLOYMENT" -n $NAMESPACE --timeout=120s
if ($LASTEXITCODE -ne 0) { Err "Rollback did not complete in time." }
Success "Rollback complete!"

# ── Post-rollback health check ────────────────────────────────────────────────
Header "Post-Rollback Health Check"
Start-Sleep -Seconds 5

Info "Pod status after rollback:"
kubectl get pods -n $NAMESPACE -l "app=$DEPLOYMENT"
Write-Host ""

Info "Updated deployment state:"
kubectl get deployment $DEPLOYMENT -n $NAMESPACE
Write-Host ""

Info "Updated rollout history:"
kubectl rollout history "deployment/$DEPLOYMENT" -n $NAMESPACE
Write-Host ""

Success "Rollback finished. Verify the API is healthy:"
Write-Host "  kubectl port-forward svc/iris-ml-api 8080:80 -n $NAMESPACE" -ForegroundColor Cyan
Write-Host "  curl http://localhost:8080/health"                           -ForegroundColor Cyan
Write-Host "  python ops/verify_deployment.py"                             -ForegroundColor Cyan