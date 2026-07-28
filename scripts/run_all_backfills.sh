#!/bin/bash

# Create output directories
mkdir -p output/backend
mkdir -p output/syslog-fluent-bit
mkdir -p output/netflow-goflow2
mkdir -p output/halo-inference
mkdir -p output/syslog-dfp
mkdir -p output/syslog-dfp-llm
mkdir -p output/netflow-dfp
mkdir -p output/frontend
mkdir -p output/config-analyzer-backend

echo "Processing ai/halo/pipelines/netflow-dfp..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/pipelines/netflow-dfp --branch dev --out output/netflow-dfp/changelog.yaml

echo "Processing ai/halo/backend..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/backend --branch dev --out output/backend/changelog.yaml

echo "Processing ai/halo/ingest/syslog-fluent-bit..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/ingest/syslog-fluent-bit --branch main --out output/syslog-fluent-bit/changelog.yaml

echo "Processing ai/halo/ingest/netflow-goflow2..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/ingest/netflow-goflow2 --branch main --out output/netflow-goflow2/changelog.yaml

echo "Processing ai/halo/training/halo-inference..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/training/halo-inference --branch main --out output/halo-inference/changelog.yaml

echo "Processing ai/halo/pipelines/syslog-dfp..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/pipelines/syslog-dfp --branch dev --out output/syslog-dfp/changelog.yaml

echo "Processing ai/halo/pipelines/syslog-dfp-llm..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/pipelines/syslog-dfp-llm --branch main --out output/syslog-dfp-llm/changelog.yaml

echo "Processing ai/halo/dashboard/frontend..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/dashboard/frontend --branch dev --out output/frontend/changelog.yaml

echo "Processing ai/halo/dashboard/config-analyzer-backend..."
python3 halo_admin_utility.py changelog backfill --repo ai/halo/dashboard/config-analyzer-backend --branch dev --out output/config-analyzer-backend/changelog.yaml

echo "All backfills complete!"
