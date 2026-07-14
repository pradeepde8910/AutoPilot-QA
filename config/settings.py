"""
Environment-specific settings.
"""
import os
from dataclasses import dataclass

@dataclass
class Settings:
    # LLM Settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    # Add your fallback Gemini API key here to handle daily rate limits:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "llama-3.3-70b-versatile")
    GEMINI_DEFAULT_MODEL: str = os.getenv("GEMINI_DEFAULT_MODEL", "gemini-2.5-flash")
    GEMINI_VISION_MODEL: str = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    
    # Browser Settings
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))
    
    # Platform Settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "")

settings = Settings()
