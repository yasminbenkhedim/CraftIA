from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from app.core.database import Base

class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(36), index=True, nullable=False)
    agent_name = Column(String(50), nullable=False)
    step_name = Column(String(100), nullable=False)
    input_text = Column(Text, nullable=True)
    output_text = Column(Text, nullable=True)
    execution_time_ms = Column(Float, default=0.0)
    status = Column(String(20), default="SUCCESS")
    created_at = Column(DateTime, default=datetime.utcnow)
