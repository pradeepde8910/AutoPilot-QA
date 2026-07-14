"""
Custom exceptions for the AI Test Engineering Platform.
"""

class QAPlatformError(Exception):
    """Base exception for all platform errors."""
    pass

class LLMReasoningError(QAPlatformError):
    """Raised when the LLM fails to return a parseable or logical response."""
    pass

class BrowserAutomationError(QAPlatformError):
    """Raised when an error occurs during Playwright execution."""
    pass

class ElementNotFoundError(BrowserAutomationError):
    """Raised when a required element is not found on the page."""
    pass

class RequirementParseError(QAPlatformError):
    """Raised when a requirement document cannot be parsed."""
    pass

class TestExecutionError(QAPlatformError):
    """Raised when a test case fails execution completely (e.g. fatal timeout)."""
    pass
