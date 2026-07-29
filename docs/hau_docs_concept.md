**Doc_Type:** Architecture
**Purpose:** The strict, universal template for all functional modules within the Halo ecosystem (Frontends, Backends, Pipelines, Ingestors, and Training scripts). This exact 13-point structure MUST be followed. If a section does not apply to the specific module, the author must keep the H2 header and explicitly write "Not applicable for this module." This ensures 100% predictable parsing.

**Visual Standard & Formatting Rules:** 
- Do not use external image files for diagrams. Use native Markdown tables or Mermaid.js syntax for visual representation.
- DO NOT include the instructional "(Mandatory)" or "(Optional)" tags in the final generated section headers. Print only the header names (e.g., "## 1. Introduction & Purpose").

**The Standard Template:**

**Doc_Type:** [ Suite | Architecture | Concept | LLM_Guide ]
**Category:** [ Assistant | Connector | Ingestor | Processor | Retriever | Framework | Utility | Ecosystem ]
**Name:** [Full Name of the Module or Concept]
**Acronym:** [3-5 Letter Identifier]
**Version:** [Semantic Versioning, e.g., 1.2.0]
**Date:** [YYYY-MM-DD]
**Author:** [Author Name(s) separated by &, e.g., Martin Kecka & Gemini AI]
**Status:** [ Draft | Active | Deprecated | Proof of Concept ]

## 1. Introduction & Purpose (Mandatory)
A high-level executive summary. What does this specific module do? What operational capability or business problem does it fulfill within the Halo ecosystem?

## 2. Architecture & Ecosystem Integration (Mandatory)
System design principles (e.g., event-driven, stateless API, hardware-deterministic), deployment context (e.g., Kubernetes pod, bare-metal GPU node, sidecar container), and ingress/egress dependencies across surrounding services. Must include a native Mermaid.js diagram or text-based DAG depicting the request or data flow.

## 3. Module File Map (Mandatory)
An exhaustive directory breakdown of the repository scope. Map every file and folder within the module, briefly describing its exact functional responsibility and operational role in the codebase.

## 4. Core Processing Lifecycle (Mandatory)
The step-by-step execution path of the primary runtime workflow. Start with the boot/initialization sequence (e.g., state restorations, cache warm-ups, or connection bootstrapping) before mapping the main operational loop. Explicitly document key payload structure changes or internal data type transitions as information passes through pipeline stages, middleware chains, or component mounting trees. Include any other lifecycle events or execution nuances critical to understanding the module's behavior.

## 5. Detailed Business Logic & Rules (Mandatory)
The core engine and brain of the module. Document the primary mathematical formulas, transformation logic, filtering mechanisms, decision trees, threshold triggers, state transitions, or authorization boundaries.

## 6. AI, LLM & Machine Learning Execution (Optional)
Details on AI/ML integration where applicable. Document neural network or LLM architectures, training/inference execution flows, prompt strategies, framework runtime settings, acceleration parameters, and model artifact lifecycles.

## 7. Data Models, State & Storage (Optional)
Internal state management, persistence strategies, and concurrency controls. Document database schemas, caching policies, state retention limits, local file-system snapshots, or in-memory data structures. Explicitly highlight thread-safety mechanisms (e.g., mutex locks, atomic swaps) and state-sharing boundaries between parallel processes. Include any other state-related mechanics or data relationships necessary for system stability.

## 8. APIs, Observability & Communication Contracts (Optional)
External communication contracts and telemetry interfaces. Document exposed HTTP/gRPC endpoints, WebSocket channels, message queue topics, health probes, Prometheus metrics, and high-level ingress/egress payload schemas (summarizing key fields and data contracts rather than dumping raw JSON blobs).

## 9. User Interface (UI) & Visualizations (Optional)
For frontend and dashboard modules. Detail the user interaction flow, component layout hierarchy, client-side state hooks, routing strategies, theme frameworks, and dynamic rendering mechanisms.

## 10. Background Services & Workers (Optional)
Asynchronous, parallel, or non-blocking background tasks running alongside the main lifecycle. Document memory/resource cleanup daemons, threaded task executors, background event listeners, scheduled CRON routines, or pre-flight warmup tasks.

## 11. CLI, Tooling & Testing (Optional)
Developer tools, diagnostic utilities, and testing frameworks bundled in the repository. Explicitly document available execution modes (e.g., unit tests, end-to-end integration tests, listening probes, or passive stream analyzers).

## 12. Configuration, Security & Hardware Affinity (Mandatory)
A structured Markdown table listing all configurable environment variables, their purpose, and default values. Document hardware requirements, runtime security boundaries, and any unconfigurable "magic numbers" or critical constants embedded directly in the codebase.

## 13. Future Enhancements & Roadmap (Mandatory)
Documented technical debt, known structural limitations, hardcoded workarounds requiring refactoring, unfulfilled aspirational features, and planned architectural evolutions.