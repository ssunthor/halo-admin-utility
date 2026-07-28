# HAU Draft Implementation Work

This document stores early drafts and concept code for the HALO Admin Utility (HAU) to ensure foundational work is preserved outside of the primary design document.

## 1. Backend: Custom Diagnostics & Health Checker
**File Path:** `backend/monitoring/health_checks.py`

```python
import time
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

diagnostics_router = APIRouter()

LATEST_LOOP_HEARTBEATS = {
    "security_kafka_consumer": time.time(),
    "netflow_kafka_consumer": time.time(),
    "janitor_worker": time.time()
}

UI_HEALTH_STATE = {
    "status": "nominal",
    "last_error": None,
    "last_error_time": 0.0
}

class UICrashReport(BaseModel):
    component: Optional[str] = "Unknown"
    error: str

class ClusterHealthChecker:
    """Evaluates health of backend dependencies including Redis, Kafka, Netbox, and vLLM."""
    def __init__(self, state_manager, netbox_url, netbox_token, vllm_endpoint, thread_pool, control_producer, topic_config):
        self.state = state_manager
        self.netbox_url = netbox_url
        self.netbox_token = netbox_token
        self.vllm_base_url = vllm_endpoint.split("/v1")[0] if "/v1" in vllm_endpoint else vllm_endpoint
        self.thread_pool = thread_pool
        self.control_producer = control_producer
        self.topics = topic_config

    async def check_redis(self, now: float, max_drift: float) -> dict:
        janitor_drift = now - LATEST_LOOP_HEARTBEATS.get("janitor_worker", now)
        janitor_ok = janitor_drift < max_drift
        
        maintenance_details = {
            "janitor_worker": {
                "status": "nominal" if janitor_ok else "stalled",
                "last_heartbeat_seconds_ago": round(janitor_drift, 2)
            }
        }

        try:
            def get_redis_stats():
                mem_info = self.state.r.info(section="memory")
                client_info = self.state.r.info(section="clients")
                
                return {
                    "used_memory_mb": round(mem_info.get("used_memory", 0) / (1024 * 1024), 2),
                    "used_memory_peak_mb": round(mem_info.get("used_memory_peak", 0) / (1024 * 1024), 2),
                    "used_memory_human": mem_info.get("used_memory_human", "0B"),
                    "connected_clients": client_info.get("connected_clients", 0)
                }

            loop = asyncio.get_running_loop()
            stats = await loop.run_in_executor(self.thread_pool, get_redis_stats)

            return {
                "status": "up" if janitor_ok else "degraded",
                "error": None,
                "metrics": stats,
                "maintenance_loops": maintenance_details
            }
        except Exception as e:
            return {
                "status": "down",
                "error": str(e),
                "metrics": {},
                "maintenance_loops": maintenance_details
            }

    async def check_kafka(self, now: float, max_drift: float) -> dict:
        sec_drift = now - LATEST_LOOP_HEARTBEATS.get("security_kafka_consumer", now)
        nf_drift = now - LATEST_LOOP_HEARTBEATS.get("netflow_kafka_consumer", now)
        
        sec_ok = sec_drift < max_drift
        nf_ok = nf_drift < max_drift
        consumers_healthy = sec_ok and nf_ok
        
        consumer_details = {
            "status": "nominal" if consumers_healthy else "stalled",
            "security_kafka_consumer": {
                "status": "nominal" if sec_ok else "stalled",
                "last_heartbeat_seconds_ago": round(sec_drift, 2)
            },
            "netflow_kafka_consumer": {
                "status": "nominal" if nf_ok else "stalled",
                "last_heartbeat_seconds_ago": round(nf_drift, 2)
            }
        }

        try:
            def get_metadata():
                cluster_metadata = self.control_producer.list_topics(timeout=2.0)
                if not cluster_metadata or not cluster_metadata.brokers:
                    return {
                        "status": "down", 
                        "error": "No reachable brokers", 
                        "consumers": consumer_details,
                        "topics": {}
                    }
                
                existing_topics = set(cluster_metadata.topics.keys())
                topic_details = {}
                all_topics_exist = True
                
                for key, name in self.topics.items():
                    exists = name in existing_topics
                    topic_details[key] = {
                        "name": name,
                        "status": "exists" if exists else "missing"
                    }
                    if not exists:
                        all_topics_exist = False
                        
                return {
                    "status": "up" if (all_topics_exist and consumers_healthy) else "degraded",
                    "error": None if all_topics_exist else "Missing required topics",
                    "consumers": consumer_details,
                    "topics": topic_details
                }

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.thread_pool, get_metadata)
        except Exception as e:
            return {
                "status": "down", 
                "error": str(e), 
                "consumers": consumer_details,
                "topics": {}
            }

    async def check_netbox(self) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient(verify=False, timeout=2.0) as client:
                resp = await client.get(
                    f"{self.netbox_url}/api/status/", 
                    headers={"Authorization": f"Token {self.netbox_token}"}
                )
                return {"status": "up" if resp.status_code == 200 else "down", "error": None}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    async def check_vllm(self) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient(verify=False, timeout=2.0) as client:
                resp = await client.get(f"{self.vllm_base_url}/v1/models")
                return {"status": "up" if resp.status_code == 200 else "down", "error": None}
        except Exception as e:
            return {"status": "down", "error": str(e)}

def setup_health_routes(health_checker: ClusterHealthChecker):
    """Attaches routes to the diagnostics router utilizing the provided health checker instance."""
    @diagnostics_router.get("/api/diagnostics/health")
    async def deep_health_probe():
        now = time.time()
        max_drift = 30.0
        
        redis_task = asyncio.create_task(health_checker.check_redis(now, max_drift))
        kafka_task = asyncio.create_task(health_checker.check_kafka(now, max_drift))
        netbox_task = asyncio.create_task(health_checker.check_netbox())
        vllm_task = asyncio.create_task(health_checker.check_vllm())
        
        redis_res, kafka_res, netbox_res, vllm_res = await asyncio.gather(
            redis_task, kafka_task, netbox_task, vllm_task
        )

        is_optimal = (
            redis_res["status"] == "up" and 
            kafka_res["status"] == "up" and 
            netbox_res["status"] == "up"
        )

        return {
            "status": "optimal" if is_optimal else "degraded",
            "timestamp": now,
            "ui_health": UI_HEALTH_STATE,
            "redis": redis_res,
            "kafka": kafka_res,
            "netbox": netbox_res,
            "vllm": vllm_res
        }

    @diagnostics_router.post("/api/diagnostics/ui-crash")
    async def report_ui_crash(report: UICrashReport):
        UI_HEALTH_STATE["status"] = "degraded"
        UI_HEALTH_STATE["last_error"] = report.error
        UI_HEALTH_STATE["last_error_time"] = time.time()
        return {"status": "logged"}

    return diagnostics_router
```

### Main Application Integration
**File Path:** `backend/main.py`
This replaces the inline monitoring logic and simply mounts the router right before startup events, injecting the live environment state.

```python
from monitoring.health_checks import ClusterHealthChecker, setup_health_routes, LATEST_LOOP_HEARTBEATS

topic_config = {
    "security": TOPIC_SECURITY,
    "netflow": TOPIC_NETFLOW,
    "netflow_v9": TOPIC_NETFLOW_V9,
    "control": CONTROL_TOPIC
}

health_checker = ClusterHealthChecker(
    state_manager=state,
    netbox_url=NETBOX_URL,
    netbox_token=NETBOX_TOKEN,
    vllm_endpoint=VLLM_ENDPOINT,
    thread_pool=thread_pool,
    control_producer=control_producer,
    topic_config=topic_config
)

app.include_router(setup_health_routes(health_checker))
```

## 2. Frontend: UI Crash Reporting Hooks

### Main Application Entry Point
**File Path:** `frontend/src/main.jsx`

```javascript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

window.addEventListener('unhandledrejection', (event) => {
  const apiBase = window._env_?.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE_URL || '';
  fetch(`${apiBase}/api/diagnostics/ui-crash`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      component: 'UnhandledPromiseRejection', 
      error: event.reason?.toString() || 'Unknown Promise Failure' 
    })
  }).catch(() => {});
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### Global Error Boundary
**File Path:** `frontend/src/App.jsx` (or dedicated component)

```javascript
import React from 'react';
import { AlertTriangle } from 'lucide-react'; // Example icon import

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught error:", error, errorInfo);
    
    const apiBase = window._env_?.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE_URL || '';
    fetch(`${apiBase}/api/diagnostics/ui-crash`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            component: 'ErrorBoundary', 
            error: error.toString() 
        })
    }).catch(() => {});
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 bg-red-900/20 border border-red-500 rounded text-red-500 h-full flex flex-col items-center justify-center">
          <AlertTriangle size={48} className="mb-4" />
          <h2 className="text-lg font-bold">Widget Crash</h2>
          <pre className="text-xs mt-2 opacity-75">{this.state.error.toString()}</pre>
          <button 
            onClick={() => this.setState({ hasError: false })}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-500"
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
```
