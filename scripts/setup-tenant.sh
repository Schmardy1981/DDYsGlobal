#!/usr/bin/env bash
###############################################################################
# DDYs Global - New Tenant Provisioning Script
#
# Usage:
#   ./scripts/setup-tenant.sh <tenant_id> <tenant_name> <admin_email> [environment]
#
# Example:
#   ./scripts/setup-tenant.sh swiss-trust-ag "Swiss Trust AG" admin@swisstrust.ch prod
###############################################################################

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TENANT_ID="${1:-}"
TENANT_NAME="${2:-}"
ADMIN_EMAIL="${3:-}"
ENVIRONMENT="${4:-prod}"
REGION="europe-west6"

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

###############################################################################
# Validate Arguments
###############################################################################
if [ -z "$TENANT_ID" ] || [ -z "$TENANT_NAME" ] || [ -z "$ADMIN_EMAIL" ]; then
    echo "Usage: $0 <tenant_id> <tenant_name> <admin_email> [environment]"
    echo ""
    echo "Arguments:"
    echo "  tenant_id     Unique identifier (lowercase, alphanumeric, hyphens)"
    echo "  tenant_name   Display name of the tenant (bank/institution)"
    echo "  admin_email   Email for the initial tenant admin user"
    echo "  environment   dev|staging|prod (default: prod)"
    echo ""
    echo "Example:"
    echo "  $0 swiss-trust-ag \"Swiss Trust AG\" admin@swisstrust.ch prod"
    exit 1
fi

# Validate tenant_id format
if ! echo "$TENANT_ID" | grep -qE '^[a-z0-9][a-z0-9-]{2,30}[a-z0-9]$'; then
    log_error "Invalid tenant_id. Must be 4-32 chars, lowercase alphanumeric and hyphens."
    exit 1
fi

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
    if [ -z "$PROJECT_ID" ]; then
        log_error "Could not extract project_id from $tfvars_file"
        exit 1
    fi

    gcloud config set project "$PROJECT_ID" --quiet
    log_info "Project: $PROJECT_ID | Environment: $ENVIRONMENT"
}

###############################################################################
# Create Tenant GCS Bucket
###############################################################################
create_bucket() {
    local bucket_name="ddys-${ENVIRONMENT}-${TENANT_ID}-documents"

    log_info "Creating GCS bucket: $bucket_name"

    # Check if bucket already exists
    if gcloud storage buckets describe "gs://${bucket_name}" &>/dev/null; then
        log_warn "Bucket $bucket_name already exists. Skipping creation."
        return 0
    fi

    gcloud storage buckets create "gs://${bucket_name}" \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --uniform-bucket-level-access \
        --default-storage-class=STANDARD \
        --quiet

    # Set versioning
    gcloud storage buckets update "gs://${bucket_name}" \
        --versioning \
        --quiet

    # Set lifecycle rules (archive after 10 years for FINMA compliance)
    cat > /tmp/lifecycle-${TENANT_ID}.json <<EOF
{
  "rule": [
    {
      "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
      "condition": {"age": 3650}
    }
  ]
}
EOF
    gcloud storage buckets update "gs://${bucket_name}" \
        --lifecycle-file=/tmp/lifecycle-${TENANT_ID}.json \
        --quiet
    rm -f /tmp/lifecycle-${TENANT_ID}.json

    # Set CORS
    cat > /tmp/cors-${TENANT_ID}.json <<EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "PUT", "POST", "HEAD"],
    "responseHeader": ["Content-Type", "Content-Disposition", "Content-Length"],
    "maxAgeSeconds": 3600
  }
]
EOF
    gcloud storage buckets update "gs://${bucket_name}" \
        --cors-file=/tmp/cors-${TENANT_ID}.json \
        --quiet
    rm -f /tmp/cors-${TENANT_ID}.json

    # Grant Cloud Run service account access
    local sa_email="ddys-${ENVIRONMENT}-run-sa@${PROJECT_ID}.iam.gserviceaccount.com"
    gcloud storage buckets add-iam-policy-binding "gs://${bucket_name}" \
        --member="serviceAccount:${sa_email}" \
        --role="roles/storage.objectUser" \
        --quiet

    # Set labels
    gcloud storage buckets update "gs://${bucket_name}" \
        --update-labels="environment=${ENVIRONMENT},tenant_id=${TENANT_ID},service=ddys-compliance,data_class=confidential,residency=switzerland" \
        --quiet

    log_ok "Bucket created: gs://${bucket_name}"
}

###############################################################################
# Create Tenant Secrets
###############################################################################
create_secrets() {
    log_info "Setting up tenant-specific secrets..."

    # Generate a tenant-specific API key
    local api_key
    api_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    local secret_id="ddys-${ENVIRONMENT}-tenant-${TENANT_ID}-api-key"

    # Check if secret already exists
    if gcloud secrets describe "$secret_id" --project="$PROJECT_ID" &>/dev/null; then
        log_warn "Secret $secret_id already exists. Skipping."
        return 0
    fi

    # Create secret
    echo -n "$api_key" | gcloud secrets create "$secret_id" \
        --project="$PROJECT_ID" \
        --replication-policy="user-managed" \
        --locations="$REGION" \
        --data-file=- \
        --labels="environment=${ENVIRONMENT},tenant_id=${TENANT_ID}" \
        --quiet

    # Grant Cloud Run SA access
    local sa_email="ddys-${ENVIRONMENT}-run-sa@${PROJECT_ID}.iam.gserviceaccount.com"
    gcloud secrets add-iam-policy-binding "$secret_id" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:${sa_email}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet

    log_ok "Tenant secret created: $secret_id"
    log_info "Tenant API Key (save this): $api_key"
}

###############################################################################
# Create Tenant Admin User via API
###############################################################################
create_admin_user() {
    log_info "Creating tenant admin user via API..."

    local backend_url
    backend_url=$(gcloud run services describe "ddys-${ENVIRONMENT}-backend" \
        --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "")

    if [ -z "$backend_url" ]; then
        log_warn "Backend URL not available. Admin user must be created manually."
        log_info "After deployment, call POST ${backend_url:-<backend_url>}/api/tenants with:"
        log_info "  tenant_id: $TENANT_ID"
        log_info "  name: $TENANT_NAME"
        log_info "  admin_email: $ADMIN_EMAIL"
        return 0
    fi

    # Check if backend is healthy
    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" "${backend_url}/api/health" 2>/dev/null || echo "000")

    if [ "$health_status" != "200" ]; then
        log_warn "Backend not healthy (HTTP $health_status). Admin user must be created manually."
        return 0
    fi

    # Create tenant via seed API (this is a simplified version)
    # In production, you'd use the admin API with proper authentication
    local response
    response=$(curl -s -X POST "${backend_url}/api/seed" \
        -H "Content-Type: application/json" \
        2>/dev/null || echo '{"error": "request failed"}')

    log_info "Seed response: $response"
    log_warn "Note: Full tenant creation with custom name/admin requires admin API access."
    log_info "Manual steps:"
    log_info "  1. Login as ADMIN"
    log_info "  2. Navigate to Admin > Tenants"
    log_info "  3. Create tenant: ID=$TENANT_ID, Name=$TENANT_NAME"
    log_info "  4. Create admin user: $ADMIN_EMAIL with BANK_USER role"
}

###############################################################################
# Seed Default Policies
###############################################################################
seed_default_policies() {
    log_info "Default policies will be created when tenant admin first logs in."
    log_info "The platform automatically seeds:"
    log_info "  - Default KYC/AML policy"
    log_info "  - Default risk matrix"
    log_info "  - Default document requirements"
    log_info "  - Default screening configuration"
    log_ok "Policy seeding configured"
}

###############################################################################
# Summary
###############################################################################
print_summary() {
    echo ""
    echo "================================================================="
    echo -e "${GREEN}  TENANT PROVISIONING COMPLETE${NC}"
    echo "================================================================="
    echo "  Tenant ID:       $TENANT_ID"
    echo "  Tenant Name:     $TENANT_NAME"
    echo "  Admin Email:     $ADMIN_EMAIL"
    echo "  Environment:     $ENVIRONMENT"
    echo "  Region:          $REGION (Zurich, Switzerland)"
    echo "  Project:         $PROJECT_ID"
    echo ""
    echo "  Resources Created:"
    echo "    - GCS Bucket:  ddys-${ENVIRONMENT}-${TENANT_ID}-documents"
    echo "    - Secret:      ddys-${ENVIRONMENT}-tenant-${TENANT_ID}-api-key"
    echo ""
    echo "  Next Steps:"
    echo "    1. Create tenant in the admin UI or via API"
    echo "    2. Set up the admin user with the provided email"
    echo "    3. Configure tenant-specific policies"
    echo "    4. Run initial screening configuration"
    echo "================================================================="
    echo ""
}

###############################################################################
# Main
###############################################################################
main() {
    echo ""
    echo "================================================================="
    echo "  DDYs Global - Tenant Provisioning"
    echo "  Tenant: $TENANT_NAME ($TENANT_ID)"
    echo "  Environment: $ENVIRONMENT"
    echo "================================================================="
    echo ""

    get_config
    create_bucket
    create_secrets
    create_admin_user
    seed_default_policies
    print_summary

    log_ok "Tenant provisioning complete!"
}

main "$@"
