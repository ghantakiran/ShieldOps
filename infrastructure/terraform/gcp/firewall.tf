###############################################################################
# ShieldOps — Firewall Rules
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Allow Health Checks (Google Cloud load balancer health check ranges)
# ---------------------------------------------------------------------------

resource "google_compute_firewall" "allow_health_check" {
  name    = "${var.project_name}-${var.environment}-allow-health-check"
  network = google_compute_network.main.id

  direction = "INGRESS"
  priority  = 1000

  source_ranges = [
    "35.191.0.0/16",
    "130.211.0.0/22",
  ]

  allow {
    protocol = "tcp"
    ports    = ["8000", "8181"]
  }

  target_tags = ["${var.project_name}-app"]

  description = "Allow Google Cloud health check probes to application instances"
}

# ---------------------------------------------------------------------------
# Allow IAP SSH (Identity-Aware Proxy for secure SSH tunneling)
# ---------------------------------------------------------------------------

resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "${var.project_name}-${var.environment}-allow-iap-ssh"
  network = google_compute_network.main.id

  direction = "INGRESS"
  priority  = 1000

  source_ranges = [
    "35.235.240.0/20",
  ]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  description = "Allow SSH via Identity-Aware Proxy"
}

# ---------------------------------------------------------------------------
# Deny All Other Ingress (catch-all deny rule)
# ---------------------------------------------------------------------------

resource "google_compute_firewall" "deny_all_ingress" {
  name    = "${var.project_name}-${var.environment}-deny-all-ingress"
  network = google_compute_network.main.id

  direction = "INGRESS"
  priority  = 65534

  source_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }

  description = "Default deny all ingress traffic"
}
