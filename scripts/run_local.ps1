# =============================================================================
# run_local.ps1 - Full local Docker workflow: build -> train -> run -> test
# Usage: .\run_local.ps1
# Requirements: Docker Desktop, Python 3.x in PATH
# =============================================================================

$IMAGE_NAME     = "iris-ml-api"
$IMAGE_TAG      = "latest"
$CONTAINER_NAME = "iris-ml-local"
$PORT           = 8080

# ── Colour helpers ────────────────────────────────────────────────────────────
function Info    { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan    }
function Success { param($msg) Write-Host "[OK]   $msg" -ForegroundColor Green   }
function Warn    { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow  }
function Err     { param($msg) Write-Host "[ERR]  $msg" -ForegroundColor Red     }
function Header  { param($msg)
    Write-Host ""
    Write-Host ("━" * 55) -ForegroundColor Magenta
    Write-Host "  $msg"   -ForegroundColor White
    Write-Host ("━" * 55) -ForegroundColor Magenta
}

# ── Abort on any error ────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

# ── Pre-flight ────────────────────────────────────────────────────────────────
Header "Pre-flight Checks"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Err "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Err "Python not found. Install Python 3 from https://www.python.org/downloads/"
    exit 1
}
$dockerVersion = docker version --format "{{.Server.Version}}" 2>$null
Info "Docker version: $dockerVersion"
Info "Python version: $(python --version)"


# ── Step 1: Train model ───────────────────────────────────────────────────────
Header "Step 1: Train Model"
Info "Installing training dependencies..."
python -m pip install -q -r requirements-train.txt

Info "Running trainer..."
python model/train.py
if ($LASTEXITCODE -ne 0) { Err "Training failed."; exit 1 }
Success "Artifacts saved to model/artifacts/"


# ── Step 2: Build Docker image ────────────────────────────────────────────────
Header "Step 2: Build Docker Image"
Info "Building ${IMAGE_NAME}:${IMAGE_TAG} ..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
if ($LASTEXITCODE -ne 0) { Err "Docker build failed."; exit 1 }

$imageInfo = docker image ls $IMAGE_NAME --format "{{.Repository}}:{{.Tag}} | Size: {{.Size}}" | Select-Object -First 1
Success "Image built: $imageInfo"


# ── Step 3: Remove existing container ────────────────────────────────────────
Header "Step 3: Clean Up Old Container"
$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $CONTAINER_NAME }
if ($existing) {
    Warn "Stopping existing container: $CONTAINER_NAME"
    docker stop $CONTAINER_NAME 2>$null | Out-Null
    docker rm   $CONTAINER_NAME 2>$null | Out-Null
}
Success "Clean"


# ── Step 4: Run container ─────────────────────────────────────────────────────
Header "Step 4: Run Container"
Info "Starting container on port $PORT..."
docker run -d `
    --name $CONTAINER_NAME `
    -p "${PORT}:8080" `
    -e ARTIFACTS_DIR=/app/model/artifacts `
    --restart unless-stopped `
    "${IMAGE_NAME}:${IMAGE_TAG}"

if ($LASTEXITCODE -ne 0) { Err "Failed to start container."; exit 1 }
Success "Container started: $CONTAINER_NAME"

# Poll /health until ready (max 30s)
Info "Waiting for container to be healthy..."
$ready = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:${PORT}/health" `
                                  -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host ""
            Success "Container is healthy! (attempt $i)"
            $ready = $true
            break
        }
    } catch {
        Write-Host -NoNewline "."
    }
}
if (-not $ready) {
    Write-Host ""
    Err "Container did not become healthy in time."
    Info "Showing container logs:"
    docker logs $CONTAINER_NAME --tail 30
    exit 1
}


# ── Step 5: Smoke tests (Invoke-RestMethod) ───────────────────────────────────
Header "Step 5: Smoke Tests"

Info "GET /health"
$health = Invoke-RestMethod -Uri "http://localhost:${PORT}/health" -Method GET
$health | ConvertTo-Json -Depth 5

Write-Host ""
Info "POST /predict -- Setosa"
$body = @{ features = @(5.1, 3.5, 1.4, 0.2) } | ConvertTo-Json
$pred = Invoke-RestMethod -Uri "http://localhost:${PORT}/predict" `
        -Method POST -Body $body -ContentType "application/json"
$pred | ConvertTo-Json -Depth 5

Write-Host ""
Info "POST /predict -- Virginica"
$body = @{ features = @(6.7, 3.0, 5.2, 2.3) } | ConvertTo-Json
$pred = Invoke-RestMethod -Uri "http://localhost:${PORT}/predict" `
        -Method POST -Body $body -ContentType "application/json"
$pred | ConvertTo-Json -Depth 5

Write-Host ""
Info "POST /predict/batch -- 3 samples"
$batchBody = @{
    features = @(
        @(5.1, 3.5, 1.4, 0.2),
        @(6.7, 3.0, 5.2, 2.3),
        @(5.8, 2.7, 4.1, 1.0)
    )
} | ConvertTo-Json -Depth 5
$batch = Invoke-RestMethod -Uri "http://localhost:${PORT}/predict/batch" `
         -Method POST -Body $batchBody -ContentType "application/json"
$batch | ConvertTo-Json -Depth 5

Write-Host ""
Info "POST /predict -- Bad input (expect 422)"
try {
    $badBody = @{ features = @(5.1, 3.5) } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:${PORT}/predict" `
        -Method POST -Body $badBody -ContentType "application/json" -ErrorAction Stop
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Success "Got expected error status: $statusCode"
}


# ── Step 6: Full Python test suite ────────────────────────────────────────────
Header "Step 6: Full Test Suite"
python test_local.py --base-url "http://localhost:${PORT}"


# ── Step 7: Summary ───────────────────────────────────────────────────────────
Header "Step 7: Container Info"
Info "Running containers:"
docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}`t{{.Image}}`t{{.Status}}`t{{.Ports}}"

Write-Host ""
Info "Container logs (last 20 lines):"
docker logs $CONTAINER_NAME --tail 20

Write-Host ""
Success "All done! Container is running at http://localhost:${PORT}"
Write-Host "  Swagger UI : http://localhost:${PORT}/docs"       -ForegroundColor Cyan
Write-Host "  Stop with  : docker stop $CONTAINER_NAME"         -ForegroundColor Cyan
Write-Host "  Logs       : docker logs -f $CONTAINER_NAME"      -ForegroundColor Cyan