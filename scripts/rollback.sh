#!/usr/bin/env bash
###############################################################################
# DDYs Global - Rollback Script
#
# Rolls back Cloud Run services to a previous revision.
#
# Usage:
#   ./scripts/rollback.sh [environment] [service] [revision]
#
# Examples:
#   ./scripts/rollback.sh prod                    # Interactive rollback
#   ./scripts/rollback.sh prod backend             # Rollback backend to previous
#   ./scripts/rollback.sh prod backend rev-abc123  # Rollback to specific revision
###############################################################################

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENVIRONMENT="${1:-prod}"
SERVICE_TYPE="${2:-}" # backend or frontend
TARGET_REVISION="${3:-}"
REGION="europe-west6"

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

###############################################################################
# Get Project Configuration
###############################################################################
get_config() {
    local tfvars_file="$PROJECT_ROOT/environments/${ENVIRONMENT}.tfvars"
    if [ ! -f "$tfvars_file" ]; then
        log_error "Environment file not found: $tfvars_file"
        exit 1
    fi

    PROJECT_ID=$(grep '^project_id' "$tfvars_file" | head -1 | sed 's/.*= *"\(.*\)"/\1/')
    gcloud config set project "$PROJECT_ID" --quiet
    log_info "Project: $PROJECT_ID | Environment: $ENVIRONMENT"
}

###############################################################################
# List Revisions
###############################################################################
list_revisions() {
    local service_name="$1"
    log_info "Available revisions for $service_name:"
    echo ""

    gcloud run revisions list \
        --service="$service_name" \
        --region="$REGION" \
        --format='table(REVISION,ACTIVE,DEPLOYED,STATUS)' \
        --sort-by='~DEPLOYED' \
        --limit=10

    echo ""
}

###############################################################################
# Rollback Service
###############################################################################
rollback_service() {
    local service_name="ddys-${ENVIRONMENT}-${1}"
    local service_type="$1"

    log_info "Rolling back $service_name..."

    # List current revisions
    list_revisions "$service_name"

    local revision="$TARGET_REVISION"

    if [ -z "$revision" ]; then
        # Get the previous revision (second most recent)
        revision=$(gcloud run revisions list \
            --service="$service_name" \
            --region="$REGION" \
            --format='value(REVISION)' \
            --sort-by='~DEPLOYED' \
            --limit=2 | tail -1)

        if [ -z "$revision" ]; then
            log_error "No previous revision found for $service_name"
            return 1
        fi

        log_info "Previous revision: $revision"
    fi

    # Confirm rollback
    if [ -t 0 ]; then
        echo ""
        read -p "$(echo -e ${YELLOW}Roll back $service_name to $revision? [y/N]: ${NC})" confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log_warn "Rollback cancelled."
            return 0
        fi
    fi

    # Perform rollback by routing 100% traffic to the previous revision
    gcloud run services update-traffic "$service_name" \
        --region="$REGION" \
        --to-revisions="$revision=100" \
        --quiet

    log_ok "$service_name rolled back to $revision"

    # Verify health
    local service_url
    service_url=$(gcloud run services describe "$service_name" \
        --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "")

    if [ -n "$service_url" ]; then
        local health_path="/api/health"
        if [ "$service_type" = "frontend" ]; then
            health_path="/"
        fi

        sleep 5
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" "${service_url}${health_path}" 2>/dev/null || echo "000")

        if [ "$status" = "200" ]; then
            log_ok "Health check passed (HTTP 200)"
        else
            log_error "Health check failed (HTTP $status). Manual verification required!"
        fi
    fi
}

###############################################################################
# Main
###############################################################################
main() {
    echo ""
    echo "================================================================="
    echo -e "${YELLOW}  DDYs Global - Service Rollback${NC}"
    echo "  Environment: $ENVIRONMENT"
    echo "  Region:      $REGION"
    echo "================================================================="
    echo ""

    get_config

    if [ -n "$SERVICE_TYPE" ]; then
        if [[ "$SERVICE_TYPE" != "backend" && "$SERVICE_TYPE" != "frontend" ]]; then
            log_error "Service must be 'backend' or 'frontend'"
            exit 1
        fi
        rollback_service "$SERVICE_TYPE"
    else
        # Interactive: rollback both or choose
        echo "Which service to rollback?"
        echo "  1) backend"
        echo "  2) frontend"
        echo "  3) both"
        echo ""
        read -p "Choice [1-3]: " choice

        case "$choice" in
            1) rollback_service "backend" ;;
            2) rollback_service "frontend" ;;
            3)
                rollback_service "backend"
                rollback_service "frontend"
                ;;
            *)
                log_error "Invalid choice."
                exit 1
                ;;
        esac
    fi

    echo ""
    log_ok "Rollback complete!"
    echo ""
    echo "To verify, check:"
    echo "  - Cloud Run Console: https://console.cloud.google.com/run?project=$PROJECT_ID"
    echo "  - Logs: https://console.cloud.google.com/logs?project=$PROJECT_ID"
    echo ""
}

main "$@"
