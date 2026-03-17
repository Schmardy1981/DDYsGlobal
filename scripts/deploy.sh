#!/usr/bin/env bash
###############################################################################
# DDYs Global Compliance Platform - Deployment Script
# One-command deployment to GCP (europe-west6, Zurich)
#
# Usage:
#   ./scripts/deploy.sh [environment]
#   ./scripts/deploy.sh dev
#   ./scripts/deploy.sh staging
#   ./scripts/deploy.sh prod
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TF_DIR="$PROJECT_ROOT/infrastructure/terraform"

ENVIRONMENT="${1:-dev}"
REGION="europe-west6"

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

###############################################################################
# Prerequisites Check
###############################################################################
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=0

    # gcloud
    if ! command -v gcloud &>/dev/null; then
        log_error "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
        missing=1
    else
        log_ok "gcloud $(gcloud version --format='value(Google Cloud SDK)' 2>/dev/null || echo 'installed')"
    fi

    # terraform
    if ! command -v terraform &>/dev/null; then
        log_error "Terraform not found. Install: https://developer.hashicorp.com/terraform/install"
        missing=1
    else
        log_ok "terraform $(terraform version -json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["terraform_version"])' 2>/dev/null || echo 'installed')"
    fi

    # docker
    if ! command -v docker &>/dev/null; then
        log_error "Docker not found. Install: https://docs.docker.com/get-docker/"
        missing=1
    else
        log_ok "docker $(docker --version | awk '{print $3}' | tr -d ',')"
    fi

    # python3
    if ! command -v python3 &>/dev/null; then
        log_error "python3 not found."
        missing=1
    else
        log_ok "python3 $(python3 --version | awk '{print $2}')"
    fi

    if [ "$missing" -ne 0 ]; then
        log_error "Missing prerequisites. Please install them and retry."
        exit 1
    fi

    # Verify gcloud auth
    if ! gcloud auth print-access-token &>/dev/null; then
        log_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    log_ok "gcloud authenticated"

    # Verify environment file
    local tfvars_file="$PROJECT_ROOT/environments/${ENVIRONMENT}.tfvars"
    if [ ! -f "$tfvars_file" ]; then
        log_error "Environment file not found: $tfvars_file"
        exit 1
    fi
    log_ok "Environment file: $tfvars_file"
}

###############################################################################
# Get Project ID from tfvars
###############################################################################
get_project_id() {
    local tfvars_file="$PROJECT_ROOT/environments/${ENVIRONMENT}.tfvars"
    PROJECT_ID=$(grep '^project_id' "$tfvars_file" | head -1 | sed 's/.*= *"\(.*\)"/\1/')
    if [ -z "$PROJECT_ID" ]; then
        log_error "Could not extract project_id from $tfvars_file"
        exit 1
    fi
    log_info "Project ID: $PROJECT_ID"
    gcloud config set project "$PROJECT_ID"
}

###############################################################################
# Configure Docker for Artifact Registry
###############################################################################
configure_docker() {
    log_info "Configuring Docker for Artifact Registry..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
    log_ok "Docker configured for ${REGION}-docker.pkg.dev"
}

###############################################################################
# Terraform: Infrastructure Provisioning
###############################################################################
run_terraform() {
    log_info "Running Terraform for environment: $ENVIRONMENT"

    cd "$TF_DIR"

    # Initialize Terraform
    log_info "terraform init..."
    terraform init \
        -backend-config="bucket=ddys-terraform-state-${PROJECT_ID}" \
        -backend-config="prefix=terraform/${ENVIRONMENT}" \
        -reconfigure

    # Plan
    log_info "terraform plan..."
    terraform plan \
        -var-file="$PROJECT_ROOT/environments/${ENVIRONMENT}.tfvars" \
        -out=tfplan

    # Confirm before apply (skip in non-interactive mode)
    if [ -t 0 ]; then
        echo ""
        read -p "$(echo -e ${YELLOW}Apply Terraform changes? [y/N]: ${NC})" confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log_warn "Terraform apply skipped."
            return 0
        fi
    fi

    # Apply
    log_info "terraform apply..."
    terraform apply tfplan

    # Capture outputs
    BACKEND_URL=$(terraform output -raw backend_url 2>/dev/null || echo "")
    FRONTEND_URL=$(terraform output -raw frontend_url 2>/dev/null || echo "")
    REGISTRY_URL=$(terraform output -raw artifact_registry_url 2>/dev/null || echo "")
    LB_IP=$(terraform output -raw load_balancer_ip 2>/dev/null || echo "")

    log_ok "Terraform applied successfully"
    rm -f tfplan

    cd "$PROJECT_ROOT"
}

###############################################################################
# Build & Push Container Images
###############################################################################
build_and_push() {
    log_info "Building and pushing container images..."

    if [ -z "$REGISTRY_URL" ]; then
        REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/ddys-${ENVIRONMENT}"
    fi

    local tag=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

    # Build backend
    log_info "Building backend image..."
    docker build \
        -f "$PROJECT_ROOT/Dockerfile.backend" \
        -t "${REGISTRY_URL}/backend:${tag}" \
        -t "${REGISTRY_URL}/backend:latest" \
        "$PROJECT_ROOT"
    log_ok "Backend image built"

    # Build frontend
    log_info "Building frontend image..."
    docker build \
        -f "$PROJECT_ROOT/Dockerfile.frontend" \
        -t "${REGISTRY_URL}/frontend:${tag}" \
        -t "${REGISTRY_URL}/frontend:latest" \
        "$PROJECT_ROOT"
    log_ok "Frontend image built"

    # Push images
    log_info "Pushing backend image..."
    docker push "${REGISTRY_URL}/backend:${tag}"
    docker push "${REGISTRY_URL}/backend:latest"
    log_ok "Backend image pushed"

    log_info "Pushing frontend image..."
    docker push "${REGISTRY_URL}/frontend:${tag}"
    docker push "${REGISTRY_URL}/frontend:latest"
    log_ok "Frontend image pushed"
}

###############################################################################
# Deploy to Cloud Run
###############################################################################
deploy_cloud_run() {
    log_info "Deploying to Cloud Run..."

    local tag=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

    if [ -z "$REGISTRY_URL" ]; then
        REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/ddys-${ENVIRONMENT}"
    fi

    # Deploy backend
    log_info "Deploying backend..."
    gcloud run deploy "ddys-${ENVIRONMENT}-backend" \
        --image="${REGISTRY_URL}/backend:${tag}" \
        --region="$REGION" \
        --platform=managed \
        --quiet

    # Deploy frontend
    log_info "Deploying frontend..."
    gcloud run deploy "ddys-${ENVIRONMENT}-frontend" \
        --image="${REGISTRY_URL}/frontend:${tag}" \
        --region="$REGION" \
        --platform=managed \
        --quiet

    log_ok "Cloud Run services deployed"
}

###############################################################################
# Seed Database (first deployment only)
###############################################################################
seed_database() {
    log_info "Checking if database needs seeding..."

    local backend_url
    backend_url=$(gcloud run services describe "ddys-${ENVIRONMENT}-backend" \
        --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "")

    if [ -z "$backend_url" ]; then
        log_warn "Could not determine backend URL. Skipping seed."
        return 0
    fi

    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" "${backend_url}/api/health" 2>/dev/null || echo "000")

    if [ "$health_status" = "200" ]; then
        log_info "Backend healthy. Triggering seed..."
        local seed_response
        seed_response=$(curl -s -X POST "${backend_url}/api/seed" 2>/dev/null || echo "failed")
        log_ok "Seed response: $seed_response"
    else
        log_warn "Backend not ready (HTTP $health_status). Seed may need manual trigger."
    fi
}

###############################################################################
# Verify Deployment
###############################################################################
verify_deployment() {
    log_info "Verifying deployment..."

    local backend_url
    backend_url=$(gcloud run services describe "ddys-${ENVIRONMENT}-backend" \
        --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "")

    local frontend_url
    frontend_url=$(gcloud run services describe "ddys-${ENVIRONMENT}-frontend" \
        --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "")

    local lb_ip
    lb_ip=$(cd "$TF_DIR" && terraform output -raw load_balancer_ip 2>/dev/null || echo "n/a")

    echo ""
    echo "================================================================="
    echo -e "${GREEN}  DEPLOYMENT SUMMARY - ${ENVIRONMENT}${NC}"
    echo "================================================================="
    echo "  Backend URL:    ${backend_url:-n/a}"
    echo "  Frontend URL:   ${frontend_url:-n/a}"
    echo "  Load Balancer:  ${lb_ip:-n/a}"
    echo "  Region:         $REGION (Zurich, Switzerland)"
    echo "  Project:        $PROJECT_ID"
    echo "================================================================="

    # Health check
    if [ -n "$backend_url" ]; then
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" "${backend_url}/api/health" 2>/dev/null || echo "000")
        if [ "$status" = "200" ]; then
            echo -e "  Backend Health: ${GREEN}HEALTHY (HTTP 200)${NC}"
        else
            echo -e "  Backend Health: ${RED}UNHEALTHY (HTTP $status)${NC}"
        fi
    fi

    if [ -n "$frontend_url" ]; then
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" "${frontend_url}/" 2>/dev/null || echo "000")
        if [ "$status" = "200" ]; then
            echo -e "  Frontend Health: ${GREEN}HEALTHY (HTTP 200)${NC}"
        else
            echo -e "  Frontend Health: ${RED}UNHEALTHY (HTTP $status)${NC}"
        fi
    fi
    echo "================================================================="
    echo ""
}

###############################################################################
# Main Execution
###############################################################################
main() {
    echo ""
    echo "================================================================="
    echo "  DDYs Global Compliance Platform - GCP Deployment"
    echo "  Environment: $ENVIRONMENT"
    echo "  Region:      $REGION (Zurich, Switzerland)"
    echo "================================================================="
    echo ""

    if [ "$ENVIRONMENT" = "prod" ]; then
        log_warn "PRODUCTION DEPLOYMENT - Please confirm this is intentional."
        if [ -t 0 ]; then
            read -p "$(echo -e ${RED}Deploy to PRODUCTION? Type 'yes' to confirm: ${NC})" confirm
            if [ "$confirm" != "yes" ]; then
                log_error "Production deployment cancelled."
                exit 1
            fi
        fi
    fi

    check_prerequisites
    get_project_id
    configure_docker
    run_terraform
    build_and_push
    deploy_cloud_run
    seed_database
    verify_deployment

    log_ok "Deployment complete!"
}

main "$@"
