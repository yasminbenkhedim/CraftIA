"""
MCP (Model Context Protocol) Schemas for VideoAgent (Phase 5).
Includes tool call parameters, governance policies, audit entries, resource metadata, and prompt templates.
"""
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    ALLOW_DRY_RUN_ONLY = "allow_dry_run_only"
    REQUIRE_CONFIRMATION = "require_confirmation"
    DENY = "deny"


class OperationPolicy(BaseModel):
    tool_name: str
    is_read_only: bool = False
    is_mutating: bool = True
    requires_checksum_validation: bool = True
    requires_approval: bool = False
    policy_decision: PolicyDecision = PolicyDecision.ALLOW


class OperationApproval(BaseModel):
    approved: bool
    approver_role: str = "user"
    confirmation_message: Optional[str] = None


class OperationAuditEntry(BaseModel):
    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    project_id: Optional[str] = None
    session_id: str = "mcp_session"
    tool_name: str
    status: str = "SUCCESS"
    execution_time_seconds: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    policy_decision: PolicyDecision = PolicyDecision.ALLOW


class OperationResult(BaseModel):
    success: bool
    tool_name: str
    project_id: Optional[str] = None
    manifest_checksum_before: Optional[str] = None
    manifest_checksum_after: Optional[str] = None
    dry_run: bool = False
    audit_entry: Optional[OperationAuditEntry] = None
    result_data: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class MCPResourceItem(BaseModel):
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


class MCPPromptItem(BaseModel):
    name: str
    description: str
    arguments: List[Dict[str, Any]] = Field(default_factory=list)
