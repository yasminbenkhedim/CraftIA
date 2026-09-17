"""
MCP Protocol REST & JSON-RPC API Endpoints for CreateFlow-AI VideoAgent.
Exposes authenticated integration surface for Model Context Protocol clients.
Enforces JWT authentication across all tool, resource, and prompt endpoints.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from backend.app.mcp.server import MCPServer
from backend.app.mcp.schemas import OperationResult
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger("uvicorn")

router = APIRouter()
mcp_server_instance = MCPServer(transport="streamable_http")


class MCPExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[Any] = 1


@router.get("/tools")
def list_mcp_tools(current_user: User = Depends(get_current_user)):
    """Returns all available MCP tools supported by the VideoAgent platform."""
    return {"tools": mcp_server_instance.list_tools(), "authenticated_user": current_user.email}


@router.post("/execute", response_model=OperationResult)
def execute_mcp_tool(req: MCPExecuteRequest, current_user: User = Depends(get_current_user)):
    """Executes a typed MCP tool against the live VideoAgent pipeline for authenticated user."""
    res = mcp_server_instance.execute_tool(req.tool_name, req.arguments, dry_run=req.dry_run)
    return res


@router.post("/jsonrpc")
def handle_jsonrpc(req: JSONRPCRequest, current_user: User = Depends(get_current_user)):
    """Standard JSON-RPC 2.0 endpoint for external MCP client integration requiring JWT Bearer token."""
    if req.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "result": {"tools": mcp_server_instance.list_tools()},
            "id": req.id
        }
    elif req.method == "tools/call":
        params = req.params or {}
        tool_name = params.get("name") or params.get("tool_name")
        arguments = params.get("arguments") or {}
        if not tool_name:
            raise HTTPException(status_code=400, detail="Missing required parameter 'name' in tools/call")
        
        res = mcp_server_instance.execute_tool(tool_name, arguments)
        return {
            "jsonrpc": "2.0",
            "result": res.model_dump(),
            "id": req.id
        }
    else:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method '{req.method}' not found"},
            "id": req.id
        }


@router.get("/resources")
def list_mcp_resources(current_user: User = Depends(get_current_user)):
    """Lists registered MCP resources for authenticated user."""
    return {"resources": mcp_server_instance.list_resources()}


@router.get("/prompts")
def list_mcp_prompts(current_user: User = Depends(get_current_user)):
    """Lists registered MCP prompts for authenticated user."""
    return {"prompts": mcp_server_instance.list_prompts()}
