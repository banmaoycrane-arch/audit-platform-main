from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class Team(Base):
    """
    团队（Team）：面向系统使用者的协作与权限边界。

    新方案定位：使用者协作组织。用于回答“谁在使用系统”“谁能看哪些账簿”。
    与 Organization 的区别：Team 是使用者组织，Organization 是被执行对象背景（客户/集团）。
    与 Ledger 的区别：Team 不直接过滤正式财务数据，Ledger 是核算数据边界。
    """
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
