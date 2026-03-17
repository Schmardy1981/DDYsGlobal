###############################################################################
# Monitoring, Alerting & Observability
###############################################################################

# --- Notification Channel ---
resource "google_monitoring_notification_channel" "email" {
  count = var.alert_email != "" ? 1 : 0

  display_name = "DDYs ${var.environment} Alert Email"
  type         = "email"
  project      = var.project_id

  labels = {
    email_address = var.alert_email
  }
}

# --- Uptime Checks ---
resource "google_monitoring_uptime_check_config" "backend_health" {
  display_name = "ddys-${var.environment}-backend-health"
  project      = var.project_id
  timeout      = "10s"
  period       = "60s"

  http_check {
    path           = "/api/health"
    port           = 443
    use_ssl        = true
    validate_ssl   = true
    request_method = "GET"

    accepted_response_status_codes {
      status_class = "STATUS_CLASS_2XX"
    }
  }

  monitored_resource {
    type = "cloud_run_revision"
    labels = {
      project_id         = var.project_id
      service_name       = google_cloud_run_v2_service.backend.name
      location           = var.region
      configuration_name = ""
      revision_name      = ""
    }
  }

  depends_on = [google_cloud_run_v2_service.backend]
}

# --- Alert Policies ---

# High error rate alert
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "DDYs ${var.environment} - High Error Rate (>5%)"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run 5xx error rate > 5%"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Backend error rate exceeds 5%. Check Cloud Run logs: https://console.cloud.google.com/run/detail/${var.region}/ddys-${var.environment}-backend/logs"
    mime_type = "text/markdown"
  }
}

# High latency alert
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "DDYs ${var.environment} - High Latency (p99 > 5s)"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run p99 latency > 5s"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/request_latencies\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5000 # 5 seconds in ms
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MAX"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []

  alert_strategy {
    auto_close = "1800s"
  }
}

# Instance count alert (scaling issues)
resource "google_monitoring_alert_policy" "max_instances" {
  display_name = "DDYs ${var.environment} - Near Max Instances"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run instance count > 80% of max"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/container/instance_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_max_instances * 0.8
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MAX"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

# Uptime check failure
resource "google_monitoring_alert_policy" "uptime_failure" {
  display_name = "DDYs ${var.environment} - Backend Down"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failing"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.labels.check_id = \"${google_monitoring_uptime_check_config.backend_health.uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "120s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []

  alert_strategy {
    auto_close = "1800s"
  }
}

# --- Log-based Metrics ---

# Count authentication failures
resource "google_logging_metric" "auth_failures" {
  name    = "ddys/${var.environment}/auth_failures"
  project = var.project_id
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"ddys-${var.environment}-backend\" AND jsonPayload.message=~\"Authentication failed|Invalid token|401\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "tenant_id"
      value_type  = "STRING"
      description = "Tenant ID from request"
    }
  }
}

# Count document uploads
resource "google_logging_metric" "document_uploads" {
  name    = "ddys/${var.environment}/document_uploads"
  project = var.project_id
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"ddys-${var.environment}-backend\" AND jsonPayload.action_key=\"document.uploaded\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# --- Dashboard ---
resource "google_monitoring_dashboard" "main" {
  dashboard_json = jsonencode({
    displayName = "DDYs ${var.environment} - Compliance Platform"
    mosaicLayout = {
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Request Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          xPos   = 6
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Request Latency (p50, p95, p99)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_99"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Instance Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MAX"
                    }
                  }
                }
                plotType = "STACKED_AREA"
              }]
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "CPU & Memory Utilization"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND metric.type = \"run.googleapis.com/container/cpu/utilizations\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_99"
                    }
                  }
                }
                plotType = "LINE"
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 8
          width  = 12
          height = 4
          widget = {
            title = "Error Logs"
            logsPanel = {
              filter = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"ddys-${var.environment}-backend\" AND severity >= ERROR"
            }
          }
        }
      ]
    }
  })

  project = var.project_id
}
