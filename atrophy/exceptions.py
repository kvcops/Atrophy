"""Custom exceptions for atrophy."""


class AtrophyError(Exception):
    """Base exception for all atrophy errors."""


class AtrophyGitError(AtrophyError):
    """Raised when a git operation fails."""


class AtrophyStorageError(AtrophyError):
    """Raised when a storage/database operation fails."""


class ProviderError(AtrophyError):
    """Raised when an LLM provider call fails."""
