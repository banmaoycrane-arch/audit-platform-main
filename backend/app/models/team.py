from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, default="firm")  # firm, virtual, enterprise
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    users = relationship("User", back_populates="team")
    ledgers = relationship("Ledger", back_populates="team")
    projects = relationship("Project", back_populates="team")
