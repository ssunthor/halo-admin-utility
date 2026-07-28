# HALO Deployment & Repository Architecture

This document outlines the standard folder structure and operational patterns for the `halo-repository`. 

The repository operates on a GitOps-based workflow, serving both as the source code repository (which builds containers via GitLab CI) and the infrastructure state (the Control Directory) for all HALO tenants and core deployments globally.

## 1. Top-Level Structure

```text
/halo-repository
├── backend/              # Pure source code for the FastAPI backend API
├── dashboard/            # Pure source code for the React/Vite frontend UI
├── ingest/               # Pure source code for ingestion services
│   ├── netflow-goflow2/  
│   └── syslog-fluent-bit/
├── pipelines/            # Pure source code for Morpheus/Triton AI pipelines
│   ├── netflow-dfp/      
│   ├── syslog-dfp/       
│   └── syslog-dfp-llm/   
├── training/             # Pure source code for AI inference & training scripts
│   └── halo-inference/   
│
└── deploy/               # The GitOps Control Directory
    ├── infrastructure/   # Global/Regional shared infrastructure components
    │   ├── netapp/       # NetApp Trident configurations (ukslo-naclu01, usnyh-naclu01)
    │   ├── kafka/        # Strimzi Kafka cluster definitions
    │   └── netbox/       # Rancher Helm configurations for Netbox deployments
    │
    ├── morpheus_runtime/ # Global AI runtime deployments
    │   ├── triton-daemonset.yaml
    │   ├── morpheus-netflow-deployment.yaml
    │   └── morpheus-logs-deployment.yaml
    │
    ├── collectors/       # Edge collector provisioning and configuration
    │   ├── cloud-init-user-data
    │   ├── docker-compose.yml
    │   ├── fluent-bit-conf/
    │   └── setup.sh
    │
    ├── base/             # Kustomize base templates shared globally
    │   ├── backend/
    │   ├── frontend/
    │   ├── ingress/
    │   ├── oauth2-proxy/ # Contains the template oauth2_proxy.yaml
    │   └── redis/        
    │
    └── tenants/          # The Geolocation Routing Layer (Tenant Deployments)
        ├── slo/          # SLO Region
        │   ├── halo-core/
        │   │   ├── kustomization.yaml
        │   │   └── oauth2_proxy.yaml
        │   ├── halo-corp/
        │   │   ├── kustomization.yaml
        │   │   ├── ingress.yaml           # e.g., corp.defensehalo.ai -> oauth_proxy
        │   │   ├── oauth2_proxy.yaml      # Customer-specific Keycloak realm config
        │   │   ├── firewall-pipeline.yaml
        │   │   └── syslog-pipeline.yaml
        │   ├── halo-demo/
        │   ├── halo-dev/
        │   └── halo-gtt3d0/
        │       └── kafka-cluster.yaml
        └── nyc/          # NYC Region
            └── halo-acme/
```

## 2. Component Guidelines

### Kubernetes Annotations (Routing & Provenance)
To ensure HAU knows where to deploy resources and to maintain strict GitOps provenance, all Kubernetes manifests (or their `kustomization.yaml`) must include the following metadata annotations:
* `halo/target-cluster`: Specifies the exact destination cluster name (e.g., `slo-hal-clu01` or `slo-aif-nvclu01`). Since the cluster name intrinsically contains the geographic location prefix (`slo`, `prg`, `nyc`), this explicitly resolves both the workload type (halo vs gpu) and the regional routing in a single variable.
* `halo/source-file`: The relative path in GitLab to the file that generated this resource (e.g., `deploy/morpheus_runtime/triton-daemonset.yaml`).

HAU will parse these annotations during the deployment phase to determine the correct Kubernetes context to target, providing a decoupled, self-describing deployment model.

### Source Code (`backend`, `dashboard`, `ingest`, `pipelines`, `training`)
* Contains actual application logic, `Dockerfile`, `requirements.txt` (or `package.json`), and unit tests.
* Governed by `.gitlab-ci.yml`. When code is merged, GitLab CI automatically builds the container images and pushes them to the GitLab Container Registry.
* Example: `pipelines/netflow-dfp/` has its own CI to build and push the `netflow-dfp` container to the registry.

### Infrastructure (`deploy/infrastructure`)
* **Kafka:** Uses the Strimzi operator. YAML files define the Kafka cluster CRD, node pools, and listeners.
* **Netbox:** Integrates via Helm. Contains the `HelmChart` configurations pointing to the Rancher Helm repository with custom HALO value overrides.
* **NetApp:** Contains Trident storage class overrides and backend configurations.

### AI Runtime (`deploy/morpheus_runtime`)
* **Triton:** Defined as a `DaemonSet` to run natively on GPU nodes for rapid inference access.
* **Morpheus Pipelines:** Shared Morpheus deployments that attach to Kafka to ingest and process tenant data.

### Edge Collectors (`deploy/collectors`)
* Used for provisioning external VMs or hardware at customer locations.
* Contains `cloud-init` templates for automated OS bootstrapping and `docker-compose` setups for running localized Fluent-Bit and parsing configurations (`parser-3164.conf`).

### Tenant Deployments (`deploy/tenants` & `deploy/base`)
* The `tenants` directory acts as the strict source of truth for deployed tenant instances. 
* Uses **Kustomize** to patch the `base/` resources.
* **OAuth2 Proxy & Keycloak:** A template for the proxy is maintained in `base/oauth2-proxy/`. For each new customer, a dedicated Keycloak realm must be created. The finalized, customer-specific `oauth2_proxy.yaml` (which ties into their unique Keycloak realm) is generated from the template and placed directly in their tenant directory.
* **Cloudflare DNS Integration:** For every new customer ingress (e.g., `corp.defensehalo.ai`), a corresponding DNS record must be dynamically provisioned in Cloudflare pointing to the cluster's ingress controller.
* Specific pipeline configurations (like `syslog-pipeline.yaml`), `oauth2_proxy.yaml` configurations, and custom `ingress.yaml` definitions (e.g. `corp.defensehalo.ai` pointing to the OAuth proxy) are explicitly mapped per tenant in their respective regional directory.
