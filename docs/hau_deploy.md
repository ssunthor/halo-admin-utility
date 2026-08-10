# HALO Deployment & Repository Architecture

This document outlines the standard folder structure and operational patterns for the `halo-repository`. 

The repository operates on a GitOps-based workflow, serving both as the source code repository (which builds containers via GitLab CI) and the infrastructure state (the Control Directory) for all HALO tenants and core deployments globally.

## 1. Top-Level Structure

```text
/halo-repository
├── backend/              # Pure source code for the FastAPI backend API
│   └── docs/             # CHANGELOG.yaml
├── dashboard/            # Pure source code for the React/Vite frontend UI
│   ├── docs-site/docs/   # CHANGELOG.yaml
│   └── frontend/docs/    # CHANGELOG.yaml
├── ingest/               # Pure source code for ingestion services
│   ├── netflow-goflow2/  
│   └── syslog-fluent-bit/
├── pipelines/            # Pure source code for Morpheus/Triton AI pipelines
│   ├── netflow-dfp/      
│   │   └── docs/         # CHANGELOG.yaml
│   ├── syslog-dfp/       
│   └── syslog-dfp-llm/   
├── training/             # Pure source code for AI inference & training scripts
│   └── halo-inference/   
│
└── deployment/           # The GitOps Control Directory & Architecture Documentation
    ├── docs/             # Centralized Design & Concept Documentation
    │   ├── ecosystem/    # Global ecosystem concept docs (e.g. halo_ecosystem.md)
    │   └── netflow-dfp/  # Component architecture docs (e.g. ndfp_design.md)
    │
    ├── infrastructure/   # Global/Regional shared infrastructure components
    │   ├── collectors/   # Edge collector provisioning and configuration
    │   ├── metallb/      # MetalLB Layer 2 load balancer IP pools & L2 advertisements
    │   ├── netapp/       # NetApp Trident configurations (ukslo-naclu01, usnyh-naclu01)
    │   └── netbox/       # Rancher Helm configurations for Netbox deployments
    │
    ├── base/             # Kustomize base templates shared globally
    │   ├── halo/         # HALO-specific applications
    │   │   ├── backend/
    │   │   ├── dashboard/
    │   │   ├── ingest/   # e.g., syslog-fluent-bit
    │   │   └── pipelines/# AI Inference Pipelines
    │   │       ├── forti-dfp/
    │   │       ├── netflow-dfp/
    │   │       ├── syslog-dfp/
    │   │       └── storage/      # Shared automated storage base (PVCs)
    │   └── vendor/       # Third-party standard components
    │       ├── kafka/        # Strimzi Kafka cluster definitions
    │       ├── oauth2-proxy/ # Contains the template oauth2_proxy.yaml
    │       ├── redis/        
    │       └── triton/       # Triton DaemonSet AI Runtime
    │
    └── tenants/          # The Geolocation Routing Layer (Tenant Deployments)
        ├── slo/          # SLO Region
        │   ├── halo-core/
        │   │   ├── kustomization.yaml
        │   │   └── oauth2_proxy.yaml
        │   ├── halo-corp/
        │   ├── halo-demo/
        │   ├── halo-dev/
        │   └── halo-gtt3d0/
        │       ├── app/
        │       │   └── kustomization.yaml
        │       └── gpu/
        │           ├── kustomization.yaml
        │           ├── storage/
        │           ├── forti-dfp/
        │           ├── netflow-dfp/
        │           └── syslog-dfp/
        │   ├── halo-demo/
        │   ├── halo-dev/

## 2. Component Guidelines

### Kubernetes Annotations (Routing & Provenance)
To ensure HAU knows where to deploy resources and to maintain strict GitOps provenance, all Kubernetes manifests (or their `kustomization.yaml`) must include the following metadata annotations:
* `halo/target-cluster`: Specifies the exact destination cluster name (e.g., `slo-hal-clu01` or `slo-aif-nvclu01`). Since the cluster name intrinsically contains the geographic location prefix (`slo`, `prg`, `nyc`), this explicitly resolves both the workload type (halo vs gpu) and the regional routing in a single variable.
* `halo/source-file`: The relative path in GitLab to the file that generated this resource (e.g., `deployment/base/vendor/triton/triton-daemonset.yaml`).

HAU will parse these annotations during the deployment phase to determine the correct Kubernetes context to target, providing a decoupled, self-describing deployment model.

### Source Code (`backend`, `dashboard`, `ingest`, `pipelines`, `training`)
* Contains actual application logic, `Dockerfile`, `requirements.txt` (or `package.json`), and unit tests.
* Governed by `.gitlab-ci.yml`. When code is merged, GitLab CI automatically builds the container images and pushes them to the GitLab Container Registry.
* Example: `pipelines/netflow-dfp/` has its own CI to build and push the `netflow-dfp` container to the registry.

### Infrastructure (`deployment/infrastructure`)
* **Netbox:** Integrates via Helm. Contains the `HelmChart` configurations pointing to the Rancher Helm repository with custom HALO value overrides.
* **NetApp:** Contains Trident storage class overrides and backend configurations for NetApp provisioning.
* **MetalLB:** Contains Layer 2 IP address pools and advertisements for local bare-metal load balancing.
* **Collectors:** Edge collector provisioning templates (`docker-compose`, `fluent-bit`).

### AI Runtime (`deployment/morpheus_runtime`)
* **Triton:** Defined as a `DaemonSet` to run natively on GPU nodes for rapid inference access.
* **Morpheus Pipelines:** Shared Morpheus deployments that attach to Kafka to ingest and process tenant data.

### Edge Collectors (`deployment/collectors`)
* Used for provisioning external VMs or hardware at customer locations.
* Contains `cloud-init` templates for automated OS bootstrapping and `docker-compose` setups for running localized Fluent-Bit and parsing configurations (`parser-3164.conf`).

### Tenant Deployments (`deployment/tenants` & `deployment/base`)
* The `tenants` directory acts as the strict source of truth for deployed tenant instances. 
* Uses **Kustomize** to patch the `base/` resources.
* **Separation of Concerns:** Tenants are split into `app/` (web, UI, backend) and `gpu/` (AI inference pipelines) to target different NodePools.
* **Automated Storage:** The `base/halo/pipelines/storage` overlay combined with Trident dynamically creates tenant PVCs (like `gtt-gtt3d0-storage`).
* **Kafka Topics & Routing:** Internal Kafka routing is explicitly defined in the bases. Topics are automatically generated via `topics.yaml` Strimzi CRDs.
* **OAuth2 Proxy & Keycloak:** A template for the proxy is maintained in `base/vendor/oauth2-proxy/`.
* **Secrets:** Handled securely via Vault integration (no raw secrets in patches).
* **Cloudflare DNS Integration:** For every new customer ingress (e.g., `corp.defensehalo.ai`), a corresponding DNS record must be dynamically provisioned in Cloudflare pointing to the cluster's ingress controller.
* Specific pipeline configurations (like `syslog-pipeline.yaml`), `oauth2_proxy.yaml` configurations, and custom `ingress.yaml` definitions (e.g. `corp.defensehalo.ai` pointing to the OAuth proxy) are explicitly mapped per tenant in their respective regional directory.