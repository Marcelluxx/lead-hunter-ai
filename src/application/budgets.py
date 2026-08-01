"""Atomic hard-budget reservations and append-only usage ledger."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.usage import normalized_cost
from ..infrastructure.models import (
    UsageBudgetModel,
    UsageLedgerModel,
    UsageReservationModel,
)
from .audit_log import append_audit_event


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetSnapshot:
    hard_limit: Decimal
    spent: Decimal
    reserved: Decimal
    warning: bool


class BudgetService:
    def reserve(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        amount: Decimal | str,
    ) -> UsageReservationModel:
        cost = normalized_cost(amount)
        budget = session.scalar(
            select(UsageBudgetModel)
            .where(UsageBudgetModel.workspace_id == workspace_id)
            .with_for_update()
        )
        if budget is None:
            raise BudgetExceeded("Budget non configurato.")
        if normalized_cost(budget.spent) + normalized_cost(budget.reserved) + cost > normalized_cost(budget.hard_limit):
            raise BudgetExceeded("Limite di spesa raggiunto.")
        reservation = UsageReservationModel(
            workspace_id=workspace_id,
            budget_id=budget.id,
            job_id=job_id,
            amount=cost,
        )
        budget.reserved = normalized_cost(budget.reserved) + cost
        session.add_all(
            [
                reservation,
                UsageLedgerModel(
                    workspace_id=workspace_id,
                    job_id=job_id,
                    entry_type="reservation",
                    amount=cost,
                ),
            ]
        )
        session.flush()
        return reservation

    def settle(
        self,
        session: Session,
        *,
        job_id: uuid.UUID,
        actual_amount: Decimal | str,
        provider: str | None = None,
        units: Decimal | str | None = None,
    ) -> BudgetSnapshot:
        actual = normalized_cost(actual_amount)
        reservation = session.scalar(
            select(UsageReservationModel)
            .where(UsageReservationModel.job_id == job_id)
            .with_for_update()
        )
        if reservation is None or reservation.state != "active":
            raise ValueError("Prenotazione non attiva.")
        if actual > normalized_cost(reservation.amount):
            raise BudgetExceeded("Il costo reale supera la prenotazione.")
        budget = session.scalar(
            select(UsageBudgetModel)
            .where(UsageBudgetModel.id == reservation.budget_id)
            .with_for_update()
        )
        assert budget is not None
        budget.reserved = normalized_cost(budget.reserved) - normalized_cost(reservation.amount)
        budget.spent = normalized_cost(budget.spent) + actual
        reservation.state = "settled"
        reservation.settled_amount = actual
        reservation.settled_at = datetime.now(timezone.utc)
        session.add(
            UsageLedgerModel(
                workspace_id=reservation.workspace_id,
                job_id=job_id,
                entry_type="charge",
                amount=actual,
                provider=provider,
                units=normalized_cost(units) if units is not None else None,
            )
        )
        released = normalized_cost(reservation.amount) - actual
        if released:
            session.add(
                UsageLedgerModel(
                    workspace_id=reservation.workspace_id,
                    job_id=job_id,
                    entry_type="release",
                    amount=released,
                )
            )
        return self._snapshot(budget)

    def release(self, session: Session, *, job_id: uuid.UUID, reason: str) -> BudgetSnapshot:
        reservation = session.scalar(
            select(UsageReservationModel)
            .where(UsageReservationModel.job_id == job_id)
            .with_for_update()
        )
        if reservation is None or reservation.state != "active":
            raise ValueError("Prenotazione non attiva.")
        budget = session.scalar(
            select(UsageBudgetModel)
            .where(UsageBudgetModel.id == reservation.budget_id)
            .with_for_update()
        )
        assert budget is not None
        amount = normalized_cost(reservation.amount)
        budget.reserved = normalized_cost(budget.reserved) - amount
        reservation.state = "released"
        reservation.settled_at = datetime.now(timezone.utc)
        session.add(
            UsageLedgerModel(
                workspace_id=reservation.workspace_id,
                job_id=job_id,
                entry_type="release",
                amount=amount,
                reason=reason[:500],
            )
        )
        return self._snapshot(budget)

    def override_limit(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        new_limit: Decimal | str,
        reason: str,
    ) -> BudgetSnapshot:
        if not reason.strip():
            raise ValueError("Motivazione obbligatoria.")
        new_value = normalized_cost(new_limit)
        budget = session.scalar(
            select(UsageBudgetModel)
            .where(UsageBudgetModel.workspace_id == workspace_id)
            .with_for_update()
        )
        if budget is None or new_value < normalized_cost(budget.spent) + normalized_cost(budget.reserved):
            raise ValueError("Nuovo limite inferiore agli impegni correnti.")
        old = normalized_cost(budget.hard_limit)
        budget.hard_limit = new_value
        session.add(
            UsageLedgerModel(
                workspace_id=workspace_id,
                entry_type="override",
                amount=new_value - old,
                reason=reason[:500],
            )
        )
        append_audit_event(
            session,
            action="budget.override",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_type="usage_budget",
            target_id=str(budget.id),
            details={"old_limit": str(old), "new_limit": str(new_value), "reason": reason},
        )
        return self._snapshot(budget)

    @staticmethod
    def _snapshot(budget: UsageBudgetModel) -> BudgetSnapshot:
        limit = normalized_cost(budget.hard_limit)
        spent = normalized_cost(budget.spent)
        reserved = normalized_cost(budget.reserved)
        ratio = (spent + reserved) / limit if limit else Decimal("1")
        return BudgetSnapshot(limit, spent, reserved, ratio >= Decimal(str(budget.warning_threshold)))
