#!/usr/bin/env python3
import os
import glob
import yaml
import re

BASE_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment/tenants"

def extract_input_topic(tenant_dir, pipeline_type):
    # Search for gpu folder
    gpu_dir = os.path.join(tenant_dir, "gpu")
    if not os.path.exists(gpu_dir):
        return None
        
    for p_dir in os.listdir(gpu_dir):
        if pipeline_type in p_dir:
            patch_file = os.path.join(gpu_dir, p_dir, "patch-env.yaml")
            if os.path.exists(patch_file):
                with open(patch_file, "r") as f:
                    data = yaml.safe_load(f)
                    
                containers = data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                for c in containers:
                    for env in c.get("env", []):
                        if env.get("name") == "INPUT_TOPIC":
                            return env.get("value")
    return None

def main():
    for app_dir in glob.glob(f"{BASE_DIR}/**/app/*", recursive=True):
        if not os.path.isdir(app_dir): continue
        folder_name = os.path.basename(app_dir)
        
        if "fluent-bit" not in folder_name:
            continue
            
        tenant_dir = os.path.dirname(os.path.dirname(app_dir))
        
        topic = None
        if "syslog" in folder_name:
            topic = extract_input_topic(tenant_dir, "syslog-pipeline")
        elif "firewall" in folder_name:
            topic = extract_input_topic(tenant_dir, "firewall-pipeline")
            
        if not topic:
            # Fallback if not found
            tenant_name = os.path.basename(tenant_dir)
            prefix = tenant_name.replace("halo-", "gtt-")
            if "syslog" in folder_name:
                topic = f"{prefix}-syslog-input"
            else:
                topic = f"{prefix}-syslog-firewall-input"
                
        print(f"Updating {folder_name} for {tenant_dir} with topic {topic}")
        
        # Write fluent-bit.conf
        fluent_conf = f"""[SERVICE]
    Flush        1
    Log_Level    info
    Parsers_File /fluent-bit/etc/parsers.conf

[INPUT]
    Name         syslog
    Mode         udp
    Listen       0.0.0.0
    Port         514
    Parser       custom-syslog
    Tag          syslog.raw

[OUTPUT]
    Name                kafka
    Match               *
    Brokers             10.250.133.29:9092,10.250.133.30:9092,10.250.133.31:9092
    Topics              {topic}
    message_key_field   host
    rdkafka.linger.ms   500
    rdkafka.compression.type lz4
"""
        with open(os.path.join(app_dir, "fluent-bit.conf"), "w") as f:
            f.write(fluent_conf)
            
        # Write parsers.conf
        parsers_conf = """[PARSER]
    Name        custom-syslog
    Format      regex
    # Nested capture: Grabs the entire line as 'message', but also extracts 'host'
    Regex       ^(?<message>(?:<\\d+>)?(?:[A-Z][a-z]{2}\\s+\\d+\\s+\\d{2}:\\d{2}:\\d{2})\\s+(?<host>\\S+).*)$
"""
        with open(os.path.join(app_dir, "parsers.conf"), "w") as f:
            f.write(parsers_conf)

if __name__ == "__main__":
    main()
