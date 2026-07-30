"""Modelli di dominio indipendenti da UI e provider esterni."""

from .audit import AuditValidationError, WebsiteAuditResult

__all__ = ["AuditValidationError", "WebsiteAuditResult"]
