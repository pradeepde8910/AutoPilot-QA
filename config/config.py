"""
Configuration entry point.
Combines settings and constants for easier importing.
"""
from config.settings import settings
from config.constants import *

def validate_config():
    """Validate that the necessary environment variables and paths exist."""
    if not settings.GROQ_API_KEY:
        import warnings
        warnings.warn("GROQ_API_KEY is not set. API calls will fail.")

# Validate config on import
validate_config()
