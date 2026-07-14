"""
Structured logging module.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
import json

from config.constants import LOGS_DIR

def setup_logger(name: str) -> logging.Logger:
    """Sets up a logger that outputs to console and a structured JSON log file."""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)

    # Console Handler (Human Readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    console_handler.setFormatter(console_format)

    # File Handler (JSON Structured)
    log_file = LOGS_DIR / f"execution_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Custom JSON Formatter
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno
            }
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_record)

    file_handler.setFormatter(JsonFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# Default platform logger
log = setup_logger("qa_platform")
