"""Public contract for loading proprietary audit prompts at runtime.

The default prompt implementation intentionally lives outside the public
repository.  Keeping the import behind this boundary lets the application and
its tests be imported from a clean checkout without publishing prompt content.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol, runtime_checkable


DEFAULT_PROMPT_MODULE = "src.prompts"


class PromptProviderUnavailable(RuntimeError):
    """Raised when the configured proprietary prompt bundle cannot be loaded."""


@runtime_checkable
class AuditPromptProvider(Protocol):
    """Prompt capabilities required by :class:`src.auditor.LeadAuditor`."""

    @property
    def system_no_website(self) -> str: ...

    @property
    def system_website_audit(self) -> str: ...

    @property
    def system_page_clean(self) -> str: ...

    def build_no_website_prompt(
        self,
        business_name: str,
        category: str,
        competitor: str,
        review_text: str,
    ) -> str: ...

    def build_website_audit_prompt(
        self,
        business_name: str,
        category: str,
        rating: float,
        review_count: int,
        pages_content: str,
    ) -> str: ...

    def build_page_clean_prompt(
        self,
        page_url: str,
        label: str,
        content: str,
    ) -> str: ...


@dataclass(frozen=True)
class ModuleAuditPromptProvider:
    """Adapter for a private Python module implementing the prompt contract."""

    module: ModuleType
    module_name: str

    @classmethod
    def load(cls, module_name: str = DEFAULT_PROMPT_MODULE) -> "ModuleAuditPromptProvider":
        normalized = module_name.strip()
        if not normalized:
            raise PromptProviderUnavailable("Il modulo dei prompt non e configurato.")
        try:
            module = importlib.import_module(normalized)
        except (ImportError, ModuleNotFoundError) as exc:
            raise PromptProviderUnavailable(
                "Bundle prompt proprietario non disponibile. "
                "Installare o montare il provider privato nel runtime server."
            ) from exc

        provider = cls(module=module, module_name=normalized)
        provider.validate()
        return provider

    def validate(self) -> None:
        for name in (
            "SYSTEM_NO_WEBSITE",
            "SYSTEM_WEBSITE_AUDIT",
            "SYSTEM_PAGE_CLEAN",
        ):
            value = getattr(self.module, name, None)
            if not isinstance(value, str) or not value.strip():
                raise PromptProviderUnavailable(
                    f"Il bundle prompt configurato non implementa {name}."
                )

        for name in (
            "build_no_website_prompt",
            "build_website_audit_prompt",
            "build_page_clean_prompt",
        ):
            if not callable(getattr(self.module, name, None)):
                raise PromptProviderUnavailable(
                    f"Il bundle prompt configurato non implementa {name}()."
                )

    @property
    def system_no_website(self) -> str:
        return self.module.SYSTEM_NO_WEBSITE

    @property
    def system_website_audit(self) -> str:
        return self.module.SYSTEM_WEBSITE_AUDIT

    @property
    def system_page_clean(self) -> str:
        return self.module.SYSTEM_PAGE_CLEAN

    def build_no_website_prompt(
        self,
        business_name: str,
        category: str,
        competitor: str,
        review_text: str,
    ) -> str:
        return self.module.build_no_website_prompt(
            business_name,
            category,
            competitor,
            review_text,
        )

    def build_website_audit_prompt(
        self,
        business_name: str,
        category: str,
        rating: float,
        review_count: int,
        pages_content: str,
    ) -> str:
        return self.module.build_website_audit_prompt(
            business_name,
            category,
            rating,
            review_count,
            pages_content,
        )

    def build_page_clean_prompt(
        self,
        page_url: str,
        label: str,
        content: str,
    ) -> str:
        return self.module.build_page_clean_prompt(page_url, label, content)


def load_prompt_provider(
    module_name: str = DEFAULT_PROMPT_MODULE,
) -> AuditPromptProvider:
    """Load and validate the private prompt provider only when it is needed."""

    return ModuleAuditPromptProvider.load(module_name)
