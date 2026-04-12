# k8s_deploy.ps1

param(
    [switch]$SkipBuild,
    [switch]$DryRun
)

$NAMESPACE = "dock8s-namespace"
$DEPLOYMENT = "dock8s-api"
$IMAGE = "faidoonjan/dock8s:latest"
$K8S_DIR = "./k8s"

function Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Success($msg) { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Error($msg) { Write-Host "[ERR]  $msg" -ForegroundColor Red; exit 1 }
function Header($msg) { Write-Host "`n=== $msg ===" -ForegroundColor White }

$KUBECTL_FLAGS = ""
if ($DryRun) { $KUBECTL_FLAGS = "--dry-run=client" }

# Step 0: Pre-flight
Header "Step 0: Pre-flight Checks"

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Error "kubectl not found"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Error "docker not found"
}

$context = kubectl config current-context
Info "Current context: $context"

if ($context -like "*prod*") {
    Warn "⚠️ You are targeting PRODUCTION: $context"
    $confirm = Read-Host "Continue? (y/N)"
    if ($confirm -ne "y") { exit }
}

# Step 1: Docker build
Header "Step 1: Docker Image"

if (-not $SkipBuild) {
    Info "Building image: $IMAGE"
    docker build -t $IMAGE .
    Success "Image built"
}
else {
    Warn "Skipping build"
}

if ($context -like "*minikube*") {
    Info "Loading image into minikube..."
    minikube image load $IMAGE
    Success "Loaded into minikube"
}

# Step 2: Apply manifests
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
        kubectl apply -f $path $KUBECTL_FLAGS
        Success "$manifest applied"
    }
    else {
        Warn "Missing: $path"
    }
}

# Step 3: Rollout
if (-not $DryRun) {
    Header "Step 3: Wait for Rollout"
    kubectl rollout status deployment/$DEPLOYMENT `
        -n $NAMESPACE `
        --timeout=120s
    Success "Rollout complete"
}

# Step 4: Verify
Header "Step 4: Verify Pods"

kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT

kubectl get deployment $DEPLOYMENT -n $NAMESPACE
kubectl get svc -n $NAMESPACE
kubectl get hpa -n $NAMESPACE
kubectl get ingress -n $NAMESPACE

# Step 5: Access
Header "Step 5: Access"

Write-Host "kubectl port-forward svc/iris-ml-api 8080:80 -n $NAMESPACE"
Write-Host "curl http://localhost:8080/health"

Success "Deployment complete!"
