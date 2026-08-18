from core.database.sql_reader import SQLReader
from core.config import Config
config = Config()
reader = SQLReader(config)
log = reader.get_git_release_audit_log("2724c624")
print("job_details keys:", list(log.job_details_json.keys()))
print("trace_logs len:", len(log.job_details_json.get("trace_logs", [])))
