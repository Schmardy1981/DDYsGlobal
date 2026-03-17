###############################################################################
# VPC & Networking - Swiss-only infrastructure
###############################################################################

# Custom VPC
resource "google_compute_network" "main" {
  name                    = "ddys-${var.environment}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis["compute.googleapis.com"]]
}

# Primary subnet in Zurich
resource "google_compute_subnetwork" "primary" {
  name                     = "ddys-${var.environment}-subnet-zurich"
  project                  = var.project_id
  network                  = google_compute_network.main.id
  region                   = var.region
  ip_cidr_range            = var.vpc_cidr_primary
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Serverless VPC Access connector (Cloud Run -> VPC)
resource "google_vpc_access_connector" "serverless" {
  name          = "ddys-${var.environment}-connector"
  project       = var.project_id
  region        = var.region
  ip_cidr_range = var.vpc_cidr_serverless
  network       = google_compute_network.main.name
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.apis["vpcaccess.googleapis.com"]]
}

# Cloud NAT for outbound internet access from VPC
resource "google_compute_router" "nat_router" {
  name    = "ddys-${var.environment}-nat-router"
  project = var.project_id
  network = google_compute_network.main.id
  region  = var.region
}

resource "google_compute_router_nat" "nat" {
  name                               = "ddys-${var.environment}-nat"
  project                            = var.project_id
  router                             = google_compute_router.nat_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# --- Firewall Rules ---

# Allow internal communication within VPC
resource "google_compute_firewall" "allow_internal" {
  name    = "ddys-${var.environment}-allow-internal"
  project = var.project_id
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [var.vpc_cidr_primary]
  priority      = 1000
}

# Allow health checks from GCP load balancer ranges
resource "google_compute_firewall" "allow_health_checks" {
  name    = "ddys-${var.environment}-allow-healthchecks"
  project = var.project_id
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["8000", "80", "443"]
  }

  source_ranges = [
    "130.211.0.0/22",  # GCP Health Check ranges
    "35.191.0.0/16",
  ]
  priority = 900
}

# Deny all other ingress by default (implicit in GCP, but explicit for clarity)
resource "google_compute_firewall" "deny_all_ingress" {
  name    = "ddys-${var.environment}-deny-all-ingress"
  project = var.project_id
  network = google_compute_network.main.name

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  priority      = 65534
}

# Private Service Connection for MongoDB Atlas VPC Peering
resource "google_compute_global_address" "private_services" {
  name          = "ddys-${var.environment}-private-svc-range"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]

  depends_on = [google_project_service.apis["servicenetworking.googleapis.com"]]
}
