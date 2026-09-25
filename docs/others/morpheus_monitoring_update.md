# Morpheus Pipeline Metrics Refactoring Handover

## Current Architecture Limitations

After a code review of the existing Morpheus pipelines (e.g., `netflow-dfp` and `syslog-dfp`), we've identified several logging and monitoring limitations:

### 1. Inconsistent Monitoring Stages
While pipelines like `syslog-dfp` utilize the built-in Morpheus `MonitorStage` to print `Window EPS` to `stdout`, other pipelines like `netflow-dfp` completely omit this stage, resulting in no EPS telemetry whatsoever.

### 2. Broken Logging Logic in NetFlow Pipeline
In `netflow-dfp/pipeline.py` (`NetflowCleanRoomStage`), the logging condition is mathematically broken:
```python
self._count += msg.payload().count
if self._count % 1000 == 0:
    logger.info(f"Clean Room: Processed {self._count} messages total")
```
Because the pipeline batch size is explicitly set to `1024`, `self._count` increments by 1024 on each iteration. The modulo `1000 == 0` condition will rarely, if ever, evaluate to true.

---

## Proposed Solution: Native Prometheus Integration

The gold-standard architectural fix is to expose pipeline throughput and loss telemetry natively via Prometheus. Since the pipelines already run a FastAPI health server on port `13005`, we can attach a `/metrics` endpoint to it.

### Step 1: Update the Pipeline Codebase

1. **Install Dependencies:**
   Ensure `prometheus_client` is installed in the Morpheus Docker images.

2. **Expose the Metrics Route:**
   Update the existing FastAPI server in `pipeline.py` (or `morpheus_app.py` for syslog) to expose the metrics:
   ```python
   from prometheus_client import make_asgi_app, Counter, Histogram

   # Define the metrics
   PIPELINE_EVENTS_PROCESSED = Counter(
       'morpheus_pipeline_events_processed_total', 
       'Total events processed by the Morpheus pipeline',
       ['pipeline_type']
   )
   
   PIPELINE_ANOMALY_LOSS = Histogram(
       'morpheus_pipeline_anomaly_loss',
       'Distribution of AutoEncoder reconstruction loss (RawLoss)',
       ['pipeline_type'],
       buckets=(1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, float("inf"))
   )

   # Attach to FastAPI
   metrics_app = make_asgi_app()
   app.mount("/metrics", metrics_app)
   ```

3. **Instrument the Pipeline Stages:**
   Instead of trying to update everything in one place, update the specific stages where the data naturally exists.

   **For EPS (Throughput):** Update an early stage like the `CleanRoomStage` to count messages as they arrive.
   ```python
   def _process(self, msg: ControlMessage):
       if msg is not None:
           # Increment the total events processed
           PIPELINE_EVENTS_PROCESSED.labels(pipeline_type="syslog").inc(msg.payload().count)
       return msg
   ```

   **For Anomaly Loss (AI Confidence):** Update the scoring stage where the AutoEncoder `avg_raw_loss` is actually calculated.
   ```python
   def _process(self, msg: ControlMessage):
       # ... existing scoring/inference logic ...
       avg_raw_loss = calculate_average_loss(msg)
       
       # Record the anomaly score into the Prometheus histogram
       PIPELINE_ANOMALY_LOSS.labels(pipeline_type="syslog").observe(avg_raw_loss)
       return msg
   ```

### Step 2: Kubernetes ServiceMonitor Configuration

To align with the standard HAU monitoring setup (as defined in `hau_design.md`), you must ensure the pipeline Kubernetes `Service` is properly labeled so Rancher's Prometheus operator automatically discovers it.

**1. Standardize the Service Port Name:**
Ensure the port exposing `13005` in your Service is named `metrics` or `api`.

**2. Label the Services:**
Apply the mandatory HAU opt-in label to the Morpheus pipeline services.
```bash
kubectl label svc <your-pipeline-svc-name> -n halo gia-monitoring=enabled
```

**3. Deploy the ServiceMonitor:**
Create the `ServiceMonitor` in the `halo` namespace using the required `release: rancher-monitoring` label so the Prometheus operator picks it up.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: gia-morpheus-pipeline-monitor
  namespace: halo
  labels:
    release: rancher-monitoring
spec:
  selector:
    matchLabels:
      gia-monitoring: enabled
  endpoints:
  - port: metrics # This must match the port name in your pipeline Service
    path: /metrics
    interval: 15s
```

## Impact & Benefits
Because Prometheus automatically tags scraped metrics with Kubernetes metadata (like `namespace` and `pod`), we can serve both the Infrastructure team and the Tenant admins using the exact same metrics:

- **HMU Integration (Global Infrastructure):** The Health Monitor Utility (HMU) will query `sum(rate(morpheus_pipeline_events_processed_total[1m]))` to get the **aggregate throughput across all tenants**. This provides the "full picture" of cluster utilization.
- **HAU Integration (Tenant-Level):** The Halo Admin Utility (HAU) will execute targeted queries like `sum(rate(morpheus_pipeline_events_processed_total{namespace="tenant-a"}[1m]))` to get perfectly isolated throughput and anomaly telemetry natively for individual Morpheus tenant deployments. 
- **Unified Dashboards:** Halo and other frontend dashboards can overlay Morpheus throughput directly alongside Kafka throughput to immediately spot processing bottlenecks or dropped packets.
