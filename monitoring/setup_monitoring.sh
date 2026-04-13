#!/usr/bin/env bash
# =============================================================================
# monitoring/setup_monitoring.sh
# Installs kube-prometheus-stack via Helm, applies our ServiceMonitor + alerts,
# and opens Grafana with the dashboard pre-loaded.
#
# Usage:
#   chmod +x monitoring/setup_monitoring.sh
#   ./monitoring/setup_monitoring.sh
# =============================================================================

set -euo pipefail

MONITORING_NS="monitoring"
ML_NS="ml-system"

GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
header()  { echo -e "\n${BOLD}━━━ $* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }


# ── Pre-flight ────────────────────────────────────────────────────────────────
header "Pre-flight Checks"
command -v kubectl >/dev/null || { echo "kubectl required"; exit 1; }
command -v helm    >/dev/null || { echo "helm required. Install: https://helm.sh/docs/intro/install/"; exit 1; }

info "kubectl context: $(kubectl config current-context)"
info "Helm version:    $(helm version --short)"


# ── Step 1: Install kube-prometheus-stack ─────────────────────────────────────
header "Step 1: Install Prometheus + Grafana Stack"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Check if already installed
if helm list -n $MONITORING_NS | grep -q "kube-prometheus"; then
    warn "kube-prometheus already installed — upgrading..."
    helm upgrade kube-prometheus prometheus-community/kube-prometheus-stack \
        --namespace $MONITORING_NS \
        --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
        --set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false
else
    helm install kube-prometheus prometheus-community/kube-prometheus-stack \
        --namespace $MONITORING_NS \
        --create-namespace \
        --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
        --set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false \
        --wait --timeout 5m
fi

success "Prometheus stack installed in namespace: $MONITORING_NS"


# ── Step 2: Apply ServiceMonitor + PrometheusRules ────────────────────────────
header "Step 2: Apply ML API Monitoring Config"

# Ensure ml-system namespace exists
kubectl get namespace $ML_NS >/dev/null 2>&1 || kubectl create namespace $ML_NS

kubectl apply -f monitoring/prometheus-config.yaml
kubectl apply -f monitoring/alerts.yaml
success "ServiceMonitor and PrometheusRules applied"


# ── Step 3: Verify ServiceMonitor ─────────────────────────────────────────────
header "Step 3: Verify Resources"
info "ServiceMonitors in $ML_NS:"
kubectl get servicemonitor -n $ML_NS 2>/dev/null || warn "No ServiceMonitors found (CRD may still be initializing)"

info "PrometheusRules in $ML_NS:"
kubectl get prometheusrule -n $ML_NS 2>/dev/null || warn "No PrometheusRules found"

info "Pods in $MONITORING_NS:"
kubectl get pods -n $MONITORING_NS


# ── Step 4: Import Grafana dashboard ──────────────────────────────────────────
header "Step 4: Grafana Dashboard"
info "To import the dashboard:"
echo "  1. Port-forward Grafana:"
echo "     kubectl port-forward svc/kube-prometheus-grafana 3000:80 -n $MONITORING_NS"
echo ""
echo "  2. Open http://localhost:3000"
echo "     Login: admin / prom-operator"
echo ""
echo "  3. Go to: Dashboards → Import → Upload JSON file"
echo "     File: monitoring/grafana-dashboard.json"
echo ""


# ── Step 5: Port-forward shortcuts ───────────────────────────────────────────
header "Step 5: Access URLs"
echo ""
echo -e "  ${CYAN}Grafana:${NC}"
echo "    kubectl port-forward svc/kube-prometheus-grafana 3000:80 -n $MONITORING_NS"
echo "    → http://localhost:3000  (admin / prom-operator)"
echo ""
echo -e "  ${CYAN}Prometheus UI:${NC}"
echo "    kubectl port-forward svc/kube-prometheus-kube-prome-prometheus 9090:9090 -n $MONITORING_NS"
echo "    → http://localhost:9090"
echo ""
echo -e "  ${CYAN}Alertmanager:${NC}"
echo "    kubectl port-forward svc/kube-prometheus-kube-prome-alertmanager 9093:9093 -n $MONITORING_NS"
echo "    → http://localhost:9093"
echo ""
echo -e "  ${CYAN}ML API metrics (direct):${NC}"
echo "    kubectl port-forward svc/iris-ml-api 8080:80 -n $ML_NS"
echo "    → http://localhost:8080/metrics"
echo ""

success "🎉 Monitoring setup complete!"


# ── Step 6: Sample PromQL queries ─────────────────────────────────────────────
header "Useful PromQL Queries (paste into Prometheus UI)"
cat << 'EOF'

  # Request rate per endpoint
  sum(rate(iris_api_requests_total[5m])) by (endpoint)

  # p95 latency across all endpoints
  histogram_quantile(0.95, sum(rate(iris_api_request_duration_seconds_bucket[5m])) by (le))

  # Error rate
  sum(rate(iris_api_requests_total{http_status=~"5.."}[5m]))
  /
  sum(rate(iris_api_requests_total[5m]))

  # Predictions by class
  sum(rate(iris_api_predictions_total[5m])) by (predicted_class)

  # Average model confidence
  sum(rate(iris_api_prediction_confidence_sum[5m])) by (predicted_class)
  /
  sum(rate(iris_api_prediction_confidence_count[5m])) by (predicted_class)

  # Model inference latency p95 (pure model, no HTTP)
  histogram_quantile(0.95, sum(rate(iris_api_prediction_duration_seconds_bucket[5m])) by (le))

  # Validation errors
  rate(iris_api_validation_errors_total[5m])

  # Requests in flight
  sum(iris_api_requests_in_progress) by (endpoint)

EOF