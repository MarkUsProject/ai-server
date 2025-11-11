# OpenTelemetry Setup: Configuration Deep Dive

### config.yml (OpenTelemetry Collector Configuration)

```yaml
# OpenTelemetry Collector Configuration for ai-server monitoring
receivers:
  # Receives telemetry from your Flask app via OTLP protocol
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317  # Your Flask app sends traces here
      http:
        endpoint: 0.0.0.0:4318  # Alternative HTTP endpoint (not currently used)
```

**Explanation:**

**`receivers` section:**
- **Purpose**: Defines how the collector receives telemetry data
- **`otlp`**: OpenTelemetry Protocol - the standard protocol for sending telemetry
  - **`grpc`**: Uses gRPC protocol (binary, efficient)
    - **`endpoint: 0.0.0.0:4317`**:
      - `0.0.0.0` means "listen on all network interfaces" (localhost, Docker bridge, etc.)
      - Port `4317` is the standard OTLP gRPC port
      - Your Flask app is configured to send to `http://localhost:4317`
  - **`http`**: Alternative HTTP endpoint (fallback, not used by your Flask app)

---

```yaml
connectors:
  # spanmetrics connector - Generates RED metrics (calls, errors, duration) from traces
  # This is what Jaeger SPM requires to function
  spanmetrics:
    histogram:
      explicit:
        # Latency buckets in seconds (0.001s = 1ms, 10s = 10000ms)
        buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
    dimensions:
      # Group metrics by these span attributes
      - name: http.method         # GET, POST, etc.
      - name: http.status_code    # 200, 500, etc.
    metrics_flush_interval: 15s   # Export metrics every 15 seconds
```

**Explanation:**

**`connectors` section:**
- **Purpose**: Connectors sit between pipelines and transform data
- **`spanmetrics`**: A special connector that watches traces and generates metrics

**How spanmetrics works:**
1. **Watches the traces pipeline**: Every span that flows through gets analyzed
2. **Generates counters**: For each span, increments `calls_total` counter
3. **Generates histograms**: Records span duration in `duration_*` histogram buckets
4. **Outputs to metrics pipeline**: The generated metrics become inputs for the metrics pipeline

**`histogram.explicit.buckets`:**
- Defines latency buckets for histogram metrics
- Values are in **seconds**: `0.001` = 1ms, `1` = 1000ms, `10` = 10000ms
- When a request takes 234ms (0.234s), it gets counted in the `0.25` bucket
- These buckets allow calculating percentiles (P50, P95, P99)

**`dimensions`:**
- Creates separate metric series for each unique combination of these attributes
- Example: `calls_total{http.method="POST", http.status_code="200"}` vs `calls_total{http.method="GET", http.status_code="404"}`
- Allows filtering metrics by HTTP method, status code, etc. in queries

**`metrics_flush_interval`:**
- How often spanmetrics exports accumulated metrics (15 seconds)
- Balances freshness vs efficiency (too frequent = overhead, too slow = stale data)

---

```yaml
processors:
  # Batches spans together for efficient export (reduces network calls)
  batch:
    timeout: 10s              # Send batch every 10 seconds
    send_batch_size: 100      # OR when 100 spans accumulate
```

**Explanation:**

**`processors` section:**
- **Purpose**: Processes/transforms telemetry data in the pipeline
- **`batch`**: Groups multiple spans/metrics together before exporting

**Why batching matters:**
- **Without batching**: Every span would be sent individually (1 network call per span)
- **With batching**: 100 spans sent in 1 network call
- **Result**: ~100x reduction in network overhead

**`timeout: 10s`:**
- If 10 seconds pass without reaching 100 spans, send whatever we have
- Prevents data from sitting too long

**`send_batch_size: 100`:**
- As soon as 100 spans accumulate, send immediately (don't wait for timeout)
- Prevents memory buildup during high traffic

**Decision logic:**
```
IF (accumulated_spans >= 100) OR (time_since_last_send >= 10s)
  THEN send_batch()
```

---

```yaml
exporters:
  # Console output - still shows traces in terminal for debugging
  debug:
    verbosity: normal

  # OTLP exporter - sends traces to Jaeger via OTLP protocol
  # Jaeger has a built-in OTLP receiver (mapped to host port 14317)
  otlp:
    endpoint: localhost:14317  # Jaeger's OTLP receiver (Docker port mapping)
    tls:
      insecure: true           # No TLS encryption (ok for local development)

  # Prometheus exporter - exposes metrics in Prometheus format
  # Prometheus will scrape this endpoint every 15 seconds
  prometheus:
    endpoint: "0.0.0.0:8889"   # Expose metrics for Prometheus to scrape
    namespace: "ai_server"      # Prefix for all metrics (ai_server_http_requests_total)
    const_labels:               # Labels added to all metrics
      environment: "development"
```

**Explanation:**

**`exporters` section:**
- **Purpose**: Defines where to send processed telemetry data

**1. `debug` exporter:**
- **Purpose**: Prints telemetry to console/logs (useful for troubleshooting)
- **`verbosity: normal`**: Shows span details without overwhelming output
  - `basic`: Just counts (least verbose)
  - `normal`: Readable span summaries ← We use this
  - `detailed`: Full JSON dumps (most verbose)

**2. `otlp` exporter:**
- **Purpose**: Sends traces to Jaeger
- **`endpoint: localhost:14317`**:
  - Jaeger container exposes port 4317 internally
  - Docker maps it to host port 14317 (`-p 14317:4317`)
  - Collector (running on host) connects to `localhost:14317`
- **`tls.insecure: true`**:
  - Disables TLS certificate verification
  - **Only safe for local development!** Production should use proper TLS

**3. `prometheus` exporter:**
- **Purpose**: Exposes metrics in Prometheus format for scraping
- **How it works**: Creates an HTTP server that Prometheus polls
- **`endpoint: "0.0.0.0:8889"`**:
  - Opens HTTP server on all interfaces, port 8889
  - Prometheus scrapes `http://localhost:8889/metrics`
- **`namespace: "ai_server"`**:
  - Adds prefix to all metric names
  - Example: `http_server_duration` → `ai_server_http_server_duration`
  - The spanmetrics connector also includes "traces_span_metrics" in its path
  - Final metric: `ai_server_traces_span_metrics_calls_total`
- **`const_labels`**:
  - These labels are added to **every metric** from this exporter
  - `environment: "development"` allows filtering by environment in queries
  - Useful when you have dev/staging/prod all sending to same Prometheus

---

```yaml
service:
  pipelines:
    # Traces pipeline - receives traces from Flask, sends to Jaeger AND spanmetrics
    traces:
      receivers: [otlp]                    # Receive traces from Flask app
      processors: [batch]                  # Batch the spans
      exporters: [debug, otlp, spanmetrics]  # Send to console, Jaeger, AND spanmetrics connector
```

**Explanation:**

**`service.pipelines` section:**
- **Purpose**: Defines the data flow through the collector
- **Think of it as**: `input → processing → output`

**Traces pipeline flow:**
```
Flask OTLP → [otlp receiver] → [batch processor] → {
                                                      [debug exporter] → Console
                                                      [otlp exporter] → Jaeger
                                                      [spanmetrics connector] → metrics/spanmetrics pipeline
                                                    }
```

**Key insight**: `spanmetrics` appears in **exporters** list
- **Why?** Connectors bridge pipelines - they're both an exporter (from traces pipeline) and a receiver (for metrics pipeline)
- **Result**: Traces flow into spanmetrics, which generates metrics and sends them to the metrics pipeline

---

```yaml
    # Spanmetrics-generated metrics pipeline - RED metrics for Jaeger SPM
    metrics/spanmetrics:
      receivers: [spanmetrics]             # Receive metrics generated from traces by spanmetrics connector
      processors: [batch]
      exporters: [prometheus]              # Export to Prometheus (Jaeger reads from here)
```

**Explanation:**

**`metrics/spanmetrics` pipeline:**
- **Name format**: `<signal>/<identifier>` allows multiple pipelines of same type
- **Purpose**: Handles metrics that spanmetrics generates from traces

**Pipeline flow:**
```
[spanmetrics connector] → [batch processor] → [prometheus exporter] → port 8889
                                                                           ↓
                                                                      Prometheus scrapes
                                                                           ↓
                                                                      Jaeger queries for SPM
```

**Why separate from main metrics pipeline?**
- Different sources: spanmetrics vs Flask instrumentation
- Different purposes: RED metrics vs detailed HTTP metrics
- Cleaner configuration: Easy to disable/modify independently

---

```yaml
    # Application-generated metrics pipeline - HTTP instrumentation metrics from Flask
    metrics:
      receivers: [otlp]                    # Receive metrics from Flask instrumentation
      processors: [batch]
      exporters: [debug, prometheus]       # Send to console AND Prometheus
```

**Explanation:**

**`metrics` pipeline (Flask-generated):**
- **Purpose**: Handles metrics that Flask OpenTelemetry instrumentation generates
- **Source**: Your Flask app's `MeterProvider` sends these via OTLP

**What metrics flow through here:**
- `ai_server_http_server_duration_milliseconds_*`: Request latency histogram
- `ai_server_http_server_active_requests`: Current active requests gauge

**Pipeline flow:**
```
Flask OTLP → [otlp receiver] → [batch processor] → {
                                                      [debug exporter] → Console
                                                      [prometheus exporter] → port 8889
                                                    }
```

**Both metrics pipelines export to same Prometheus endpoint:**
- spanmetrics: RED metrics (calls_total, duration_bucket)
- Flask: HTTP instrumentation metrics (http_server_duration)
- **Result**: All metrics available at `http://localhost:8889/metrics`

---

```yaml
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug]                   # Only console for now
```

**Explanation:**

**`logs` pipeline:**
- **Currently simple**: Just receives and prints to console
- **Future expansion**: Could add exporters for:
  - Loki (log aggregation system, part of Grafana stack)
  - Elasticsearch
  - CloudWatch, Datadog, etc.

---

### prometheus.yml (Prometheus Scrape Configuration)

```yaml
# Prometheus configuration for scraping OpenTelemetry Collector metrics
global:
  scrape_interval: 15s      # How often to scrape metrics
  evaluation_interval: 15s  # How often to evaluate rules
```

**Explanation:**

**`global` section:**
- **Purpose**: Default settings for all scrape jobs

**`scrape_interval: 15s`:**
- How often Prometheus fetches metrics from targets
- Every 15 seconds, Prometheus sends HTTP GET to `http://localhost:8889/metrics`
- **Trade-off**:
  - Shorter interval (5s) = fresher data, more load
  - Longer interval (60s) = less frequent updates, less overhead
  - 15s is a good balance for local development

**`evaluation_interval: 15s`:**
- How often to evaluate alerting rules (not used in our setup)
- Kept at same interval as scraping for simplicity

---

```yaml
# Scrape configuration
scrape_configs:
  # Scrape metrics from OpenTelemetry Collector
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['host.docker.internal:8888']  # Collector's metrics endpoint
        labels:
          service: 'otel-collector'
```

**Explanation:**

**`scrape_configs` section:**
- **Purpose**: Defines what endpoints to scrape and how

**Job 1: `otel-collector`:**
- **Purpose**: Scrape collector's own internal metrics (health, performance)
- **`targets: ['host.docker.internal:8888']`**:
  - `host.docker.internal`: Docker's way to reach host machine from container
  - Port `8888`: Collector's self-monitoring endpoint (built-in)
  - **What's scraped**: Collector health, queue sizes, processing rates, etc.
- **`labels: {service: 'otel-collector'}`**:
  - Adds `service="otel-collector"` label to all scraped metrics
  - Allows filtering: `up{service="otel-collector"}`

---

```yaml
  # Scrape metrics that the collector exports (from your Flask app)
  - job_name: 'ai-server'
    static_configs:
      - targets: ['host.docker.internal:8889']  # We'll expose metrics here
        labels:
          service: 'ai-server'
```

**Explanation:**

**Job 2: `ai-server`:**
- **Purpose**: Scrape application metrics (spanmetrics + Flask HTTP metrics)
- **`targets: ['host.docker.internal:8889']`**:
  - Same host resolution mechanism
  - Port `8889`: Where our Prometheus exporter exposes metrics
  - **What's scraped**:
    - `ai_server_traces_span_metrics_calls_total`
    - `ai_server_http_server_duration_*`
    - All metrics from both pipelines
- **`labels: {service: 'ai-server'}`**:
  - Adds `service="ai-server"` label
  - Note: Metrics already have `service_name="ai-server"` from spanmetrics
  - Both labels coexist (useful for different query patterns)

---

## Summary: The Complete Picture

### Data Flow with All Components:

```
Flask App (ai-server)
  ↓ OpenTelemetry SDK (server.py lines 26-59)
  ↓ Generates: Traces (spans) + Metrics (HTTP instrumentation)
  ↓ Sends via: OTLP gRPC to localhost:4317
  ↓
OpenTelemetry Collector (config.yml)
  ↓
  ├─ Traces Pipeline:
  │   ├─ otlp receiver (port 4317) receives spans
  │   ├─ batch processor groups them
  │   └─ Exporters:
  │       ├─ debug → Console logs
  │       ├─ otlp (port 14317) → Jaeger (for trace visualization)
  │       └─ spanmetrics connector → Generates RED metrics
  │             ↓
  │   ┌────────┘
  │   ↓
  ├─ Metrics/spanmetrics Pipeline:
  │   ├─ spanmetrics connector outputs metrics
  │   ├─ batch processor groups them
  │   └─ prometheus exporter (port 8889) → Exposes /metrics endpoint
  │
  └─ Metrics Pipeline:
      ├─ otlp receiver receives HTTP metrics from Flask
      ├─ batch processor groups them
      └─ Exporters:
          ├─ debug → Console logs
          └─ prometheus exporter (port 8889) → Same endpoint as spanmetrics
               ↓
Prometheus (prometheus.yml)
  ↓ Scrapes http://host.docker.internal:8889/metrics every 15s
  ↓ Stores time-series data
  ↓
Jaeger SPM (docker-compose.yml)
  ↓ Queries Prometheus: http://prometheus:9090
  ↓ Looks for: ai_server_traces_span_metrics_calls_total
  ↓ Displays: RED metrics in Monitor tab
```

### Key Takeaways:

1. **spanmetrics is essential** for Jaeger SPM - it converts traces to metrics
2. **Namespace configuration must match** between collector and Jaeger
3. **Connectors bridge pipelines** - spanmetrics sits between traces and metrics
4. **Prometheus is the middle layer** - stores metrics that Jaeger queries
5. **All components must be on same network** (or use host.docker.internal)
6. **Multiple exporters can coexist** - same pipeline can output to console + Jaeger + Prometheus
