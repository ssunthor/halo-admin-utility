import sys
import os
import glob
import logging
from datetime import datetime
from typing import Dict, Any

_LOGGING_CONFIGURED = False

class MultiProcessSafeDailyLogger(logging.FileHandler):
    def __init__(self, base_filename, backup_count=14, encoding='utf-8'):
        self.base_filename = base_filename
        self.backup_count = backup_count
        super().__init__(self._get_filename(), mode='a', encoding=encoding)

    def _get_filename(self):
        today_str = datetime.now().strftime('%Y-%m-%d')
        return f"{self.base_filename}.{today_str}"

    def emit(self, record):
        new_filename = self._get_filename()
        if self.baseFilename != os.path.abspath(new_filename):
            self.close()
            self.baseFilename = os.path.abspath(new_filename)
            self.stream = self._open()
            self._cleanup_old_logs()
        super().emit(record)

    def _cleanup_old_logs(self):
        if self.backup_count <= 0:
            return
        try:
            dir_name = os.path.dirname(self.base_filename)
            base_name = os.path.basename(self.base_filename)
            pattern = os.path.join(dir_name, f"{base_name}.*")
            files = sorted(glob.glob(pattern))
            
            if len(files) > self.backup_count:
                files_to_delete = files[:-self.backup_count]
                for f in files_to_delete:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
        except Exception:
            pass

def setup_logging(config: Dict[str, Any]):
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    log_cfg = config.get("logging", {})
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    backup_count_days = log_cfg.get("backup_count_days", 14)
    
    log_datefmt = '%Y-%m-%d %H:%M:%S'
    log_format = '%(asctime)s - %(levelname)-5s - [%(name)s] - %(message)s'
    formatter = logging.Formatter(log_format, datefmt=log_datefmt)

    console_level_str = log_cfg.get("level", "INFO").upper()
    configured_level = getattr(logging, console_level_str, logging.INFO)

    is_server_mode = 'start-grpc-server' in sys.argv

    console_handler = logging.StreamHandler(sys.stdout)
    if is_server_mode:
        console_handler.setLevel(configured_level)
    else:
        console_handler.setLevel(logging.WARNING)

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_cfg.get("enable_file_logging", False):
        try:
            base_log_dir = log_cfg["directory"]
            if not os.path.isabs(base_log_dir):
                base_log_dir = os.path.join(project_root, base_log_dir)
            os.makedirs(base_log_dir, exist_ok=True)
            
            app_log_filename = log_cfg["app_log_filename"]
            err_log_filename = log_cfg["error_log_filename"]
            
            app_log_path = os.path.join(base_log_dir, app_log_filename)
            app_file_handler = MultiProcessSafeDailyLogger(app_log_path, backup_count=backup_count_days, encoding='utf-8')
            app_file_handler.setLevel(logging.DEBUG)
            app_file_handler.setFormatter(formatter)
            root_logger.addHandler(app_file_handler)

            err_log_path = os.path.join(base_log_dir, err_log_filename)
            err_file_handler = MultiProcessSafeDailyLogger(err_log_path, backup_count=backup_count_days, encoding='utf-8')
            err_file_handler.setLevel(logging.WARNING)
            err_file_handler.setFormatter(formatter)
            root_logger.addHandler(err_file_handler)

        except Exception as e:
            logging.error(f"Failed to configure file logging: {e}", exc_info=True)

    for noisy_logger in ["hpack", "httpx", "httpcore", "urllib3", "zeep", "requests"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True