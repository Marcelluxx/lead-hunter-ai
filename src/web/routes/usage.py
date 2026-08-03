from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...application.authentication import AuthContext
from ...application.authorization import AuthorizationDenied, require_permission
from ...domain.identity import Permission
from ...domain.usage import normalized_cost
from ...infrastructure.models import UsageBudgetModel
from ..dependencies import WebRuntime, current_auth, db_session, runtime, workspace_uuid
from ..schemas import BudgetOverrideRequest, BudgetResponse


router = APIRouter(prefix="/workspaces/{workspace_id}/usage", tags=["usage"])


@router.get("/budget", response_model=BudgetResponse)
def get_budget(
    workspace_id: str,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
):
    workspace = workspace_uuid(workspace_id)
    try:
        require_permission(
            session,
            user_id=context.user_id,
            workspace_id=workspace,
            permission=Permission.VIEW_RESULTS,
            mfa_verified=context.mfa_verified,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    budget = session.scalar(
        select(UsageBudgetModel).where(UsageBudgetModel.workspace_id == workspace)
    )
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget non trovato.")
    limit = normalized_cost(budget.hard_limit)
    spent = normalized_cost(budget.spent)
    reserved = normalized_cost(budget.reserved)
    ratio = (spent + reserved) / limit if limit else Decimal("1")
    return BudgetResponse(
        hard_limit=limit,
        spent=spent,
        reserved=reserved,
        warning=ratio >= Decimal(str(budget.warning_threshold)),
    )


@router.put("/budget", response_model=BudgetResponse)
def override_budget(
    workspace_id: str,
    body: BudgetOverrideRequest,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    workspace = workspace_uuid(workspace_id)
    try:
        require_permission(
            session,
            user_id=context.user_id,
            workspace_id=workspace,
            permission=Permission.MANAGE_BUDGET,
            mfa_verified=context.mfa_verified,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return app.budgets.override_limit(
        session,
        workspace_id=workspace,
        actor_user_id=context.user_id,
        new_limit=body.hard_limit,
        reason=body.reason,
    )
