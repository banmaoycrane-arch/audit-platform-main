from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.user_ledger_auth import UserLedgerAuth


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    platform_role: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
    agreed_terms: Mapped[bool] = mapped_column(Boolean, default=False)
    agreed_privacy: Mapped[bool] = mapped_column(Boolean, default=False)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    last_ledger_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ledgers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team: Mapped["Team"] = relationship("Team", back_populates="users")
    ledger_auths: Mapped[list["UserLedgerAuth"]] = relationship(
        "UserLedgerAuth", foreign_keys="UserLedgerAuth.user_id", back_populates="user"
    )
