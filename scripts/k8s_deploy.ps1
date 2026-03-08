# =============================================================================
# k8s_deploy.ps1 - Apply all K8s manifests and verify deployment health
#
# Usage:
#   .\k8s_deploy.ps1                   # full deploy
#   .\k8s_deploy.ps1 -SkipBuild        # skip docker build
#   .\k8s_deploy.ps1 -DryRun           # kubectl dry-run only (no changes)
# =============================================================================

param(
    [switch]$SkipBuild,
    [switch]$DryRun
)

$NAMESPACE  = "ml-system"
$DEPLOYMENT = "dock8s-api"
$IMAGE      = "dock8s:latest"
$K8S_DIR    = ".\k8s"

# ── Colour helpers ────────────────────────────────────────────────────────────
function Info    { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan    }
function Success { param($msg) Write-Host "[OK]   $msg" -ForegroundColor Green   }
function Warn    { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow  }
function Err     { param($msg) Write-Host "[ERR]  $msg" -ForegroundColor Red; exit 1 }
function Header  { param($msg)
    Write-Host ""
    Write-Host ("━" * 55) -ForegroundColor Magenta
    Write-Host "  $msg"   -ForegroundColor White
    Write-Host ("━" * 55) -ForegroundColor Magenta
}

$ErrorActionPreference = "Stop"
$KubectlFlags = if ($DryRun) { "--dry-run=client" } else { "" }


# ── Step 0: Pre-flight checks ─────────────────────────────────────────────────
Header "Step 0: Pre-flight Checks"

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Err "kubectl not found. Install via: winget install Kubernetes.kubectl"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Err "docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop"
}

$k8sVer = kubectl version --client --short 2>$null | Select-Object -First 1
Info "kubectl: $k8sVer"

$context = kubectl config current-context 2>$null
Info "Current context: $context"

# Safety check for production clusters
if ($context -match "prod") {
    Warn "You are targeting a PRODUCTION context: $context"
    $confirm = Read-Host "Continue? (y/N)"
    if ($confirm -ne "y") { exit 0 }
}


# ── Step 1: Build & load Docker image ────────────────────────────────────────
Header "Step 1: Docker Image"
if (-not $SkipBuild) {
    Info "Building image: $IMAGE"
    docker build -t $IMAGE .
    if ($LASTEXITCODE -ne 0) { Err "Docker build failed." }
    Success "Image built"
} else {
    Warn "Skipping build (-SkipBuild)"
}

# Load into minikube if that's the active context
if ($context -match "minikube") {
    Info "Loading image into minikube..."
    minikube image load $IMAGE
    if ($LASTEXITCODE -ne 0) { Err "Failed to load image into minikube." }
    Success "Image loaded into minikube"
}


# ── Step 2: Apply manifests in order ─────────────────────────────────────────
Header "Step 2: Apply Kubernetes Manifests"

$manifests = @(
    "namespace.yaml",
    "configmap.yaml",
    "deployment.yaml",
    "service.yaml",
    "hpa.yaml",
    "ingress.yaml"
)

foreach ($manifest in $manifests) {
    $path = Join-Path $K8S_DIR $manifest
    if (Test-Path $path) {
        Info "Applying $manifest..."
        if ($KubectlFlags) {
            kubectl apply -f $path $KubectlFlags
        } else {
            kubectl apply -f $path
        }
        if ($LASTEXITCODE -ne 0) { Err "Failed to apply $manifest" }
        Success "$manifest applied"
    } else {
        Warn "Skipping missing file: $path"
    }
}


# ── Step 3: Wait for rollout ──────────────────────────────────────────────────
if (-not $DryRun) {
    Header "Step 3: Wait for Rollout"
    Info "Waiting for deployment rollout (timeout: 120s)..."
    kubectl rollout status "deployment/$DEPLOYMENT" -n $NAMESPACE --timeout=120s
    if ($LASTEXITCODE -ne 0) { Err "Rollout did not complete in time." }
    Success "Rollout complete!"
}


# ── Step 4: Verify resources ──────────────────────────────────────────────────
Header "Step 4: Verify Resources"

Info "Pods:"
kubectl get pods -n $NAMESPACE -l "app=$DEPLOYMENT" -o wide
Write-Host ""

Info "Deployment:"
kubectl get deployment $DEPLOYMENT -n $NAMESPACE
Write-Host ""

Info "Services:"
kubectl get svc -n $NAMESPACE
Write-Host ""

Info "HPA:"
kubectl get hpa -n $NAMESPACE 2>$null
if ($LASTEXITCODE -ne 0) { Warn "HPA not ready yet (metrics-server may need a moment)" }
Write-Host ""

Info "Ingress:"
kubectl get ingress -n $NAMESPACE 2>$null
if ($LASTEXITCODE -ne 0) { Warn "No ingress found" }


# ── Step 5: Access instructions ───────────────────────────────────────────────
Header "Step 5: Access the API"
Write-Host ""
Write-Host "  Option A - Port-forward (quickest):" -ForegroundColor Cyan
Write-Host "    kubectl port-forward svc/iris-ml-api 8080:80 -n $NAMESPACE"
Write-Host "    Then open: http://localhost:8080/health"
Write-Host ""
Write-Host "  Option B - minikube service URL:" -ForegroundColor Cyan
Write-Host "    minikube service iris-ml-api-external -n $NAMESPACE --url"
Write-Host ""
Write-Host "  Option C - Ingress (after DNS setup):" -ForegroundColor Cyan
Write-Host "    Add to C:\Windows\System32\drivers\etc\hosts:"
Write-Host "    <minikube-ip>  iris-api.local"
Write-Host "    Then: curl http://iris-api.local/health"
Write-Host ""

# Print minikube IP if available
if ($context -match "minikube") {
    $minikubeIp = minikube ip 2>$null
    if ($minikubeIp) {
        Info "Minikube IP: $minikubeIp"
        Info "NodePort access: http://${minikubeIp}:30080/health"
    }
}

Write-Host ""
Success "Deployment complete! Namespace: $NAMESPACE"


# ── Useful follow-up commands ─────────────────────────────────────────────────
Header "Useful Commands"
Write-Host @"
  # Watch pods in real-time:
  kubectl get pods -n $NAMESPACE -w

  # View logs from all replicas:
  kubectl logs -l app=$DEPLOYMENT -n $NAMESPACE --tail=50 -f

  # Manually scale replicas:
  kubectl scale deployment $DEPLOYMENT --replicas=4 -n $NAMESPACE

  # Trigger a rolling restart (e.g. after config change):
  kubectl rollout restart deployment/$DEPLOYMENT -n $NAMESPACE

  # Roll back to previous version:
  kubectl rollout undo deployment/$DEPLOYMENT -n $NAMESPACE

  # View rollout history:
  kubectl rollout history deployment/$DEPLOYMENT -n $NAMESPACE

  # Describe a pod (for debugging):
  kubectl describe pod -l app=$DEPLOYMENT -n $NAMESPACE

  # Delete everything:
  kubectl delete namespace $NAMESPACE
"@ -ForegroundColor DarkCyan