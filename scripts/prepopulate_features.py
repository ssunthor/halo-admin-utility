#!/usr/bin/env python3
import os
import sys
import logging
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from halo_admin_utility import load_config
from core.database.database import get_engine, get_session_factory
from core.io_handlers.sql_writer import SQLWriter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-5s - [%(name)s] - %(message)s')
logger = logging.getLogger("prepopulate_features")

PRICING_DETECT = {
    "0-100": {"monthly": 600, "install": 900},
    "101-200": {"monthly": 900, "install": 1350},
    "201-500": {"monthly": 1200, "install": 1800},
    "501-1000": {"monthly": 1800, "install": 2700},
    "1001-2000": {"monthly": 2400, "install": 6000},
    "2001-5000": {"monthly": 3300, "install": 8250},
    "5001-10000": {"monthly": 4800, "install": 12000},
    "10001-20000": {"monthly": 6600, "install": 16500},
    "20001-50000": {"monthly": 9300, "install": 37200},
    "50001-100000": {"monthly": 15000, "install": 60000}
}

PRICING_CONFIG_RECON = {
    "0-4": {"monthly": 0, "install": 0},
    "0-100": {"monthly": 450, "install": 450},
    "101-200": {"monthly": 800, "install": 800},
    "201-500": {"monthly": 1400, "install": 1400},
    "501-1000": {"monthly": 2100, "install": 2100},
    "1001-2000": {"monthly": 3150, "install": 4725},
    "2001-5000": {"monthly": 4400, "install": 6600},
    "5001-10000": {"monthly": 6500, "install": 9750},
    "10001-20000": {"monthly": 10000, "install": 15000},
    "20001-50000": {"monthly": 14000, "install": 35000},
    "50001-100000": {"monthly": 21000, "install": 52500}
}

PRICING_CVE_RECON = {
    "0-100": {"monthly": 450, "install": 450},
    "101-200": {"monthly": 800, "install": 800},
    "201-500": {"monthly": 1400, "install": 1400},
    "501-1000": {"monthly": 2100, "install": 2100},
    "1001-2000": {"monthly": 3150, "install": 4725},
    "2001-5000": {"monthly": 4400, "install": 6600},
    "5001-10000": {"monthly": 6500, "install": 9750},
    "10001-20000": {"monthly": 10000, "install": 15000},
    "20001-50000": {"monthly": 14000, "install": 35000},
    "50001-100000": {"monthly": 21000, "install": 52500}
}

PRICING_HALO_RESPONSE = {
    "0-100": {"monthly": 1200, "install": 2400},
    "101-200": {"monthly": 1800, "install": 3600},
    "201-500": {"monthly": 2700, "install": 5400},
    "501-1000": {"monthly": 3600, "install": 7200},
    "1001-2000": {"monthly": 5100, "install": 17850},
    "2001-5000": {"monthly": 7200, "install": 25200},
    "5001-10000": {"monthly": 9900, "install": 34650},
    "10001-20000": {"monthly": 13200, "install": 46200},
    "20001-50000": {"monthly": 18600, "install": 111600},
    "50001-100000": {"monthly": 27600, "install": 165600}
}

# Definitions of initial features
INITIAL_FEATURES = [
    {
        "env_variable": "VITE_SHOW_OVERVIEW",
        "feature_name": "OverallAnalysis",
        "description": "Provides high-level security posture, overall threat analytics, and executive summaries.",
        "product_category": "Halo Detect",
        "ui_grouping": "Core Dashboard",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_HOST_INVENTORY",
        "feature_name": "HostInventory",
        "description": "Detailed inventory view of endpoints, OS details, and agent connection states.",
        "product_category": "Halo Detect",
        "ui_grouping": "Inventory",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_NETWORK",
        "feature_name": "Network & Firewall",
        "description": "Traditional network monitoring, traffic volumes, and firewall rule analytics.",
        "product_category": "Halo Detect",
        "ui_grouping": "Network",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_RAW_DATA",
        "feature_name": "Raw Data Explorer",
        "description": "Allows analysts to query raw, unparsed logs directly from backend data lakes for deep threat hunting.",
        "product_category": "Halo Detect",
        "ui_grouping": "Data Exploration",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_GALAXY",
        "feature_name": "NetworkGalaxy",
        "description": "A visual topological graph representation of network communications and log sources.",
        "product_category": "Halo Detect",
        "ui_grouping": "System Logs",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_DESTINATIONS",
        "feature_name": "Destinations Map",
        "description": "Visualizes external IP destinations for threat intelligence and geolocation context.",
        "product_category": "Halo Detect",
        "ui_grouping": "Global / Threat",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_LOG_DNA",
        "feature_name": "System Log DNA / Anomalies",
        "description": "Behavioral analytics and anomaly detection derived from unstructured system logs via AI pipelines.",
        "product_category": "Halo Detect",
        "ui_grouping": "System Logs",
        "gitops_dependencies": {"ai/halo/pipelines/syslog-dfp": ">=v0.2.6"},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_NETFLOW_DNA",
        "feature_name": "Network Netflow DNA",
        "description": "Threat detection and behavioral analytics derived specifically from network flow (NetFlow/sFlow) data via Morpheus DFP pipelines.",
        "product_category": "Halo Detect",
        "ui_grouping": "Netflow / Network",
        "gitops_dependencies": {"ai/halo/pipelines/netflow-dfp": ">=v0.3.0"},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_USER_ACTIVITY",
        "feature_name": "User Activity",
        "description": "Tracks identity events, logins, and detects potential insider threats or compromised credentials.",
        "product_category": "Halo Detect",
        "ui_grouping": "Identity / IAM",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_HOST_FORENSICS",
        "feature_name": "Host Forensics",
        "description": "Deep dive into endpoint activity, process trees, and localized forensic investigation data.",
        "product_category": "Halo Detect",
        "ui_grouping": "Endpoint Security",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_NETBOX",
        "feature_name": "NetboxVulnerabilities",
        "description": "Integrates with NetBox DCIM to display infrastructure vulnerabilities (CVEs) mapped to hardware inventory and network assets.",
        "product_category": "Halo Recon - CVE",
        "ui_grouping": "Vulnerability Mgmt",
        "gitops_dependencies": {},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_CONFIG_ANALYZER",
        "feature_name": "ConfigAnalyzer",
        "description": "Static analysis tool for parsing and evaluating the security of uploaded firewall/network configuration files.",
        "product_category": "Halo Recon - Configuration",
        "ui_grouping": "Config Mgmt",
        "gitops_dependencies": {"ai/halo/dashboard/config-analyzer-backend": ">=v0.1.0"},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_CONFIG_TRANSLATOR",
        "feature_name": "ConfigTranslator",
        "description": "Cross-vendor utility to convert network configurations (e.g., Cisco IOS, Palo Alto PAN-OS, Fortinet FortiOS).",
        "product_category": "Halo Recon - Configuration",
        "ui_grouping": "Config Mgmt",
        "gitops_dependencies": {"ai/halo/dashboard/config-analyzer-backend": ">=v0.1.0"},
        "is_paid_addon": True,
        "enabled_by_default": False
    },
    {
        "env_variable": "VITE_SHOW_CONFIG_BUILD_TOOL",
        "feature_name": "PolicyGenerator",
        "description": "Greenfield policy generation tool to automate the creation of new firewall/security policies based on intent.",
        "product_category": "Halo Recon - Configuration",
        "ui_grouping": "Config Mgmt",
        "gitops_dependencies": {"ai/halo/dashboard/config-analyzer-backend": ">=v0.1.0"},
        "is_paid_addon": True,
        "enabled_by_default": False
    }
]

for f in INITIAL_FEATURES:
    if f["product_category"] == "Halo Response":
        f["pricing_tiers"] = PRICING_HALO_RESPONSE
    elif f["product_category"] == "Halo Detect":
        f["pricing_tiers"] = PRICING_DETECT
    elif "CVE" in f["product_category"]:
        f["pricing_tiers"] = PRICING_CVE_RECON
    elif "Configuration" in f["product_category"]:
        f["pricing_tiers"] = PRICING_CONFIG_RECON
    else:
        f["pricing_tiers"] = {}

def main():
    config = load_config()
    write_dsn = config.get('database', {}).get('write_dsn')
    
    if not write_dsn:
        logger.error("No write_dsn found in config/settings.yaml")
        sys.exit(1)
        
    logger.info("Connecting to the database...")
    engine = get_engine(write_dsn)
    
    logger.info("Ensuring feature_catalog table exists...")
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feature_catalog (
                id VARCHAR(36) PRIMARY KEY,
                feature_name VARCHAR(255) NOT NULL,
                description TEXT,
                product_category VARCHAR(100),
                ui_grouping VARCHAR(100),
                env_variable VARCHAR(255) NOT NULL UNIQUE,
                gitops_dependencies JSON DEFAULT '{}',
                pricing_tiers JSON DEFAULT '{}',
                is_paid_addon BOOLEAN DEFAULT FALSE,
                enabled_by_default BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
            );
        """))
        
        # In case the table already exists, explicitly add the column
        conn.execute(text("ALTER TABLE feature_catalog ADD COLUMN IF NOT EXISTS pricing_tiers JSON DEFAULT '{}';"))
        
        conn.commit()
    
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()
    
    writer = SQLWriter(session)
    try:
        count = 0
        for f in INITIAL_FEATURES:
            writer.upsert_feature(
                feature_name=f["feature_name"],
                env_variable=f["env_variable"],
                description=f["description"],
                product_category=f["product_category"],
                ui_grouping=f["ui_grouping"],
                gitops_dependencies=f.get("gitops_dependencies", {}),
                pricing_tiers=f.get("pricing_tiers", {}),
                is_paid_addon=f["is_paid_addon"],
                enabled_by_default=f["enabled_by_default"]
            )
            count += 1
            
        session.commit()
        logger.info(f"Successfully prepopulated {count} features in FeatureCatalog.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to prepopulate features: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
