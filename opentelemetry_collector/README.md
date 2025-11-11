# OpenTelemetry Collector

The reason we are installing the opentelemetry contrib collector is because it includes the spanmetrics connector which is required if we wish
to enable Jaeger's Service Performance Monitoring ([SPM](https://www.jaegertracing.io/docs/2.11/architecture/spm/))

## Configuration

Take a look at `config.yml` inside this folder for a default configuration. For more information about this system
please take a look at the collector configuration [guide](https://opentelemetry.io/docs/collector/configuration/).

## Execution

Start all services with Docker Compose:
```bash
docker-compose up -d
```

## Alerting

Alerting is configured using Prometheus Alertmanager:

1. **Alert Rules** (`alert_rules.yml`) - Defines when alerts fire (high errors, latency, service down)
2. **Alertmanager** (`alertmanager.yml`) - Handles notifications and routing

### Viewing Alerts

- **Prometheus Alerts**: http://localhost:9090/alerts - See current alert status
- **Alertmanager UI**: http://localhost:9093 - View, silence, and manage active alerts

### Configuring Email Notifications

Edit `alertmanager.yml` and uncomment the email configuration:

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'your-email@gmail.com'
  smtp_auth_username: 'your-email@gmail.com'
  smtp_auth_password: 'your-app-password'

receivers:
  - name: 'default'
    email_configs:
      - to: 'your-email@example.com'
```

Then restart: `docker-compose restart alertmanager`

### Testing Alerts

To test if alerts are working, stop your Flask app and wait 3 minutes - the `ServiceDown` alert should fire.
