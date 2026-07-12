"""审计工作底稿账套：为 B1 模式凭证导入提供隔离账套。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.ledger import Ledger
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.services.shared.ledger_timeline_service import initialize_ledger_timeline
from app.services.basic_data.coa_service import init_default_accounts


def get_or_create_working_ledger(
    db: Session,
    *,
    project_id: int,
    entity_org_id: int,
    period_code: str | None = None,
) -> Ledger:
    """获取或创建项目关联的工作底稿账套。"""
    existing = (
        db.query(Ledger)
        .filter(Ledger.is_working.is_(True), Ledger.project_id == project_id)
        .order_by(Ledger.id.asc())
        .first()
    )
    if existing:
        if existing.organization_id is None:
            existing.organization_id = entity_org_id
            db.flush()
        return existing

    project = db.get(Project, project_id)
    if not project:
        raise ValueError("审计项目不存在")

    suffix = f"（{period_code}）" if period_code else ""
    ledger = Ledger(
        team_id=project.team_id,
        organization_id=entity_org_id,
        name=f"{project.name}·工作底稿{suffix}",
        status="active",
        accounting_start_date=date.today(),
        is_working=True,
        project_id=project_id,
    )
    db.add(ledger)
    db.flush()
    initialize_ledger_timeline(db, ledger, organization_name=ledger.name)
    init_default_accounts(db, ledger.id)

    member_ids = {member.user_id for member in project.members}
    if project.manager_id:
        member_ids.add(project.manager_id)
    for user_id in member_ids:
        authorize_user_to_ledger(db, ledger.id, user_id, role="accountant", granted_by=project.manager_id)

    db.commit()
    db.refresh(ledger)
    return ledger
