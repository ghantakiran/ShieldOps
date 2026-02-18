###############################################################################
# ShieldOps — Global HTTPS Load Balancer
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Static Global IP Address
# ---------------------------------------------------------------------------

resource "google_compute_global_address" "main" {
  name         = "${var.project_name}-${var.environment}-lb-ip"
  address_type = "EXTERNAL"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Serverless Network Endpoint Group (Cloud Run)
# ---------------------------------------------------------------------------

resource "google_compute_region_network_endpoint_group" "main" {
  name                  = "${var.project_name}-${var.environment}-neg"
  region                = var.gcp_region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.main.name
  }
}

# ---------------------------------------------------------------------------
# Backend Service
# ---------------------------------------------------------------------------

resource "google_compute_backend_service" "main" {
  name                  = "${var.project_name}-${var.environment}-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.main.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# ---------------------------------------------------------------------------
# URL Map (HTTPS — primary)
# ---------------------------------------------------------------------------

resource "google_compute_url_map" "main" {
  name            = "${var.project_name}-${var.environment}-url-map"
  default_service = google_compute_backend_service.main.id
}

# ---------------------------------------------------------------------------
# Managed SSL Certificate (only when domain_name is set)
# ---------------------------------------------------------------------------

resource "google_compute_managed_ssl_certificate" "main" {
  count = var.domain_name != "" ? 1 : 0

  name = "${var.project_name}-${var.environment}-ssl-cert"

  managed {
    domains = [var.domain_name]
  }
}

# ---------------------------------------------------------------------------
# HTTPS Proxy
# ---------------------------------------------------------------------------

resource "google_compute_target_https_proxy" "main" {
  count = var.domain_name != "" ? 1 : 0

  name             = "${var.project_name}-${var.environment}-https-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main[0].id]
}

# ---------------------------------------------------------------------------
# HTTPS Forwarding Rule (port 443)
# ---------------------------------------------------------------------------

resource "google_compute_global_forwarding_rule" "https" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-${var.environment}-https-rule"
  ip_address            = google_compute_global_address.main.address
  ip_protocol           = "TCP"
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_https_proxy.main[0].id
}

# ---------------------------------------------------------------------------
# HTTP → HTTPS Redirect
# ---------------------------------------------------------------------------

resource "google_compute_url_map" "http_redirect" {
  name = "${var.project_name}-${var.environment}-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  name    = "${var.project_name}-${var.environment}-http-proxy"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  name                  = "${var.project_name}-${var.environment}-http-rule"
  ip_address            = google_compute_global_address.main.address
  ip_protocol           = "TCP"
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_http_proxy.http_redirect.id
}
