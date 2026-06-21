from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, default="firm")  # firm, virtual, enterprise
    parent_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)  # 多层级组织支持
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 自关联：上级团队和子团队
    parent_team = relationship("Team", remote_side=[id], backref="sub_teams")
    
    # 关系
    users = relationship("User", back_populates="team")
    ledgers = relationship("Ledger", back_populates="team")
    projects = relationship("Project", back_populates="team")
