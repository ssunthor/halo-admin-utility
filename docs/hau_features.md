# HALO Frontend Feature Toggles (Initial Discovery)

This document contains the initial discovery of the frontend feature toggles (`VITE_SHOW_*` environment variables) currently accepted by the HALO dashboard.

In the future, this list will be replaced by a `feature-manifest.yaml` published by the frontend CI/CD pipeline and automatically synced into the HAU `FeatureCatalog` database table.

## Discovered Features (as of August 2026)

| Feature Variable                  | MVP Service Area | UI Grouping           | Expected Value | Component / Deep Description |
|-----------------------------------|------------------|-----------------------|----------------|------------------------------|
| `VITE_SHOW_OVERVIEW`              | Defense Halo Portal | Core Dashboard       | `1` or `0`     | **OverallAnalysis**: Provides high-level security posture, overall threat analytics, and executive summaries. |
| `VITE_SHOW_HOST_INVENTORY`        | Defense Halo Portal | Inventory            | `1` or `0`     | **HostInventory**: Detailed inventory view of endpoints, OS details, and agent connection states. |
| `VITE_SHOW_GALAXY`                | Defense Halo Detect Service | System Logs          | `1` or `0`     | **NetworkGalaxy**: A visual topological graph representation of network communications and log sources. |
| `VITE_SHOW_DESTINATIONS`          | Defense Halo Detect Service | Global / Threat      | `1` or `0`     | **Destinations Map**: Visualizes external IP destinations for threat intelligence and geolocation context. |
| `VITE_SHOW_LOG_DNA`               | Defense Halo Detect Service | System Logs          | `1` or `0`     | **System Log DNA / Anomalies**: Behavioral analytics and anomaly detection derived from unstructured system logs via AI pipelines. |
| `VITE_SHOW_NETFLOW_DNA`           | Defense Halo Detect Service | Netflow / Network    | `1` or `0`     | **Network Netflow DNA**: Threat detection and behavioral analytics derived specifically from network flow (NetFlow/sFlow) data via Morpheus DFP pipelines. |
| `VITE_SHOW_USER_ACTIVITY`         | Defense Halo Detect Service | Identity / IAM       | `1` or `0`     | **User Activity**: Tracks identity events, logins, and detects potential insider threats or compromised credentials. |
| `VITE_SHOW_HOST_FORENSICS`        | Defense Halo Detect Service | Endpoint Security    | `1` or `0`     | **Host Forensics**: Deep dive into endpoint activity, process trees, and localized forensic investigation data. |
| `VITE_SHOW_NETWORK`               | Defense Halo Portal | Network              | `1` or `0`     | **Network & Firewall**: Traditional network monitoring, traffic volumes, and firewall rule analytics. |
| `VITE_SHOW_NETBOX`                | Defense Halo Recon - CVE Service | Vulnerability Mgmt   | `1` or `0`     | **NetboxVulnerabilities**: Integrates with NetBox DCIM to display infrastructure vulnerabilities (CVEs) mapped to hardware inventory and network assets. |
| `VITE_SHOW_RAW_DATA`              | Defense Halo Portal | Data Exploration     | `1` or `0`     | **Raw Data Explorer**: Allows analysts to query raw, unparsed logs directly from backend data lakes for deep threat hunting. |
| `VITE_SHOW_CONFIG_ANALYZER`       | Defense Halo Recon - Configuration Service | Config Mgmt          | `1` or `0`     | **ConfigAnalyzer**: Static analysis tool for parsing and evaluating the security of uploaded firewall/network configuration files. |
| `VITE_SHOW_CONFIG_TRANSLATOR`     | Defense Halo Recon - Configuration Service | Config Mgmt          | `1` or `0`     | **ConfigTranslator**: Cross-vendor utility to convert network configurations (e.g., Cisco IOS, Palo Alto PAN-OS, Fortinet FortiOS). |
| `VITE_SHOW_CONFIG_BUILD_TOOL`     | Defense Halo Recon - Configuration Service | Config Mgmt          | `1` or `0`     | **PolicyGenerator**: Greenfield policy generation tool to automate the creation of new firewall/security policies based on intent. |
