###############################################################################
# ShieldOps — VPC & Networking
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------

resource "google_compute_network" "main" {
  name                    = "${var.project_name}-${var.environment}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Subnet
# ---------------------------------------------------------------------------

resource "google_compute_subnetwork" "main" {
  name          = "${var.project_name}-${var.environment}-subnet"
  ip_cidr_range = "10.2.0.0/20"
  region        = var.gcp_region
  network       = google_compute_network.main.id

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# ---------------------------------------------------------------------------
# Cloud Router
# ---------------------------------------------------------------------------

resource "google_compute_router" "main" {
  name    = "${var.project_name}-${var.environment}-router"
  region  = var.gcp_region
  network = google_compute_network.main.id
}

# ---------------------------------------------------------------------------
# Cloud NAT (all subnets, auto-allocate IPs)
# ---------------------------------------------------------------------------

resource "google_compute_router_nat" "main" {
  name   = "${var.project_name}-${var.environment}-nat"
  router = google_compute_router.main.name
  region = var.gcp_region

  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# ---------------------------------------------------------------------------
# Private Service Access (for Cloud SQL and Memorystore)
# ---------------------------------------------------------------------------

resource "google_compute_global_address" "private_services" {
  name          = "${var.project_name}-${var.environment}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Serverless VPC Access Connector (for Cloud Run)
# ---------------------------------------------------------------------------

resource "google_vpc_access_connector" "main" {
  name          = "${var.project_name}-${var.environment}-vpc-cx"
  region        = var.gcp_region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.8.0.0/28"

  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.apis]
}
