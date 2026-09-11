import logging
import sys
import re

class SensitiveDataFilter(logging.Filter):
    """Filters out potential API keys, passwords, and tokens from log output."""
    PATTERNS = [
        re.compile(r'(AIza[0-9A-Za-z-_]{35})'),
        re.compile(r'(sk-[a-zA-Z0-9]{20,})'),
        re.compile(r'(gsk_[a-zA-Z0-9]{20,})'),
        re.compile(r'(Bearer\s+[a-zA-Z0-9\-._~+/]+=*)', re.IGNORECASE),
        re.compile(r'(password|secret|token|api_key)["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in self.PATTERNS:
                record.msg = pattern.sub(r'***REDACTED***', str(record.msg))
        if record.args:
            cleaned_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern in self.PATTERNS:
                        arg = pattern.sub(r'***REDACTED***', arg)
                cleaned_args.append(arg)
            record.args = tuple(cleaned_args)
        return True

def setup_logging():
    logger = logging.getLogger("document_extractor")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        
    return logger

logger = setup_logging()
