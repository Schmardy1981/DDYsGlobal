###############################################################################
# HTTPS Load Balancer with Cloud Armor WAF
###############################################################################

# --- Serverless NEG for Backend ---
resource "google_compute_region_network_endpoint_group" "backend_neg" {
  name                  = "ddys-${var.environment}-backend-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.backend.name
  }
}

# --- Serverless NEG for Frontend ---
resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  name                  = "ddys-${var.environment}-frontend-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.frontend.name
  }
}

# --- Backend Services ---
resource "google_compute_backend_service" "backend" {
  name                  = "ddys-${var.environment}-backend-bs"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 300

  backend {
    group = google_compute_region_network_endpoint_group.backend_neg.id
  }

  security_policy = var.cloud_armor_enabled ? google_compute_security_policy.waf[0].id : null

  log_config {
    enable      = true
    sample_rate = 1.0
  }

  # Enable Cloud CDN for API caching (only GET responses with Cache-Control)
  enable_cdn = false
}

resource "google_compute_backend_service" "frontend" {
  name                  = "ddys-${var.environment}-frontend-bs"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 60

  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg.id
  }

  security_policy = var.cloud_armor_enabled ? google_compute_security_policy.waf[0].id : null

  log_config {
    enable      = true
    sample_rate = 0.5
  }

  # Enable Cloud CDN for static frontend assets
  enable_cdn = true
  cdn_policy {
    cache_mode                   = "CACHE_ALL_STATIC"
    default_ttl                  = 3600
    max_ttl                      = 86400
    serve_while_stale            = 86400
    signed_url_cache_max_age_sec = 0
  }
}

# --- URL Map (routing) ---
resource "google_compute_url_map" "main" {
  name            = "ddys-${var.environment}-urlmap"
  project         = var.project_id
  default_service = google_compute_backend_service.frontend.id

  host_rule {
    hosts        = var.domain_name != "" ? [var.domain_name, "*.${var.domain_name}"] : ["*"]
    path_matcher = "main"
  }

  path_matcher {
    name            = "main"
    default_service = google_compute_backend_service.frontend.id

    # Route /api/* to backend
    path_rule {
      paths   = ["/api/*", "/docs", "/redoc", "/openapi.json"]
      service = google_compute_backend_service.backend.id
    }
  }
}

# --- Managed SSL Certificate ---
resource "google_compute_managed_ssl_certificate" "main" {
  count = var.domain_name != "" ? 1 : 0

  name    = "ddys-${var.environment}-ssl-cert"
  project = var.project_id

  managed {
    domains = [var.domain_name]
  }
}

# --- HTTPS Proxy ---
resource "google_compute_target_https_proxy" "main" {
  count = var.domain_name != "" ? 1 : 0

  name             = "ddys-${var.environment}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main[0].id]

  ssl_policy = google_compute_ssl_policy.modern[0].id
}

# SSL Policy (modern, TLS 1.2+)
resource "google_compute_ssl_policy" "modern" {
  count = var.domain_name != "" ? 1 : 0

  name            = "ddys-${var.environment}-ssl-policy"
  project         = var.project_id
  profile         = "MODERN"
  min_tls_version = "TLS_1_2"
}

# --- HTTP Proxy (redirect to HTTPS) ---
resource "google_compute_url_map" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name    = "ddys-${var.environment}-http-redirect"
  project = var.project_id

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name    = "ddys-${var.environment}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect[0].id
}

# --- Global Forwarding Rules (External IPs) ---
resource "google_compute_global_address" "main" {
  name    = "ddys-${var.environment}-ip"
  project = var.project_id
}

resource "google_compute_global_forwarding_rule" "https" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "ddys-${var.environment}-https-rule"
  project               = var.project_id
  target                = google_compute_target_https_proxy.main[0].id
  ip_address            = google_compute_global_address.main.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_forwarding_rule" "http" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "ddys-${var.environment}-http-rule"
  project               = var.project_id
  target                = google_compute_target_http_proxy.http_redirect[0].id
  ip_address            = google_compute_global_address.main.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# Fallback: HTTP proxy without SSL (for dev/staging without domain)
resource "google_compute_target_http_proxy" "main_no_ssl" {
  count = var.domain_name == "" ? 1 : 0

  name    = "ddys-${var.environment}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.main.id
}

resource "google_compute_global_forwarding_rule" "http_no_ssl" {
  count = var.domain_name == "" ? 1 : 0

  name                  = "ddys-${var.environment}-http-rule"
  project               = var.project_id
  target                = google_compute_target_http_proxy.main_no_ssl[0].id
  ip_address            = google_compute_global_address.main.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# --- Cloud Armor WAF Security Policy ---
resource "google_compute_security_policy" "waf" {
  count = var.cloud_armor_enabled ? 1 : 0

  name    = "ddys-${var.environment}-waf-policy"
  project = var.project_id

  # Default rule: allow
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow rule"
  }

  # Rate limiting
  rule {
    action   = "throttle"
    priority = 1000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      rate_limit_threshold {
        count        = var.rate_limit_threshold
        interval_sec = 60
      }
    }
    description = "Rate limit: ${var.rate_limit_threshold} requests/min per IP"
  }

  # Block known malicious patterns (OWASP ModSecurity Core Rule Set)
  rule {
    action   = "deny(403)"
    priority = 100
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
    description = "Block XSS attacks"
  }

  rule {
    action   = "deny(403)"
    priority = 101
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }
    description = "Block SQL injection attacks"
  }

  rule {
    action   = "deny(403)"
    priority = 102
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('lfi-v33-stable')"
      }
    }
    description = "Block local file inclusion attacks"
  }

  rule {
    action   = "deny(403)"
    priority = 103
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('rfi-v33-stable')"
      }
    }
    description = "Block remote file inclusion attacks"
  }

  rule {
    action   = "deny(403)"
    priority = 104
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('scannerdetection-v33-stable')"
      }
    }
    description = "Block scanner detection"
  }

  # Block non-Swiss IP ranges for admin endpoints (optional, strict mode)
  # Uncomment if you want geo-restriction on admin endpoints
  # rule {
  #   action   = "deny(403)"
  #   priority = 200
  #   match {
  #     expr {
  #       expression = "request.path.matches('/api/admin/.*') && !origin.region_code == 'CH'"
  #     }
  #   }
  #   description = "Admin access restricted to Swiss IPs"
  # }

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
    }
  }
}
