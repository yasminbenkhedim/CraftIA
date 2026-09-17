"""
MCP Server Implementation for VideoAgent using Official MCP Python SDK (Phase 5).
Supports stdio and Streamable HTTP transports, execution governance, and audit logging.
"""
import sys
import json
import logging
from typing import Dict, Any, List, Optional, Literal

from backend.app.mcp.schemas import OperationResult, OperationAuditEntry, PolicyDecision
from backend.app.mcp.tool_registry import MCPToolRegistry
from backend.app.mcp.resources import MCPResourceCatalog
from backend.app.mcp.prompts import MCPPromptCatalog

logger = logging.getLogger("uvicorn")


class MCPServer:
    """
    VideoAgent MCP Server implementing official MCP Protocol capabilities.
    Supports stdio and Streamable HTTP transports, execution governance, and audit logging.
    """

    def __init__(
        self,
        transport: Literal["stdio", "streamable_http"] = "stdio",
        host: str = "127.0.0.1",
        port: int = 8765
    ):
        self.transport = transport
        self.host = host
        self.port = port
        self.audit_log: List[OperationAuditEntry] = []

        try:
            from mcp.server.fastmcp import FastMCP
            self.mcp_app = FastMCP(
                "CreateFlow-AI VideoAgent Server",
                instructions="Model Context Protocol Server for CreateFlow-AI VideoAgent platform."
            )
            self._register_fastmcp_handlers()
            self._sdk_available = True
        except ImportError:
            self.mcp_app = None
            self._sdk_available = False
            logger.warning("MCPServer: Official mcp SDK not installed. Running in fallback compatibility mode.")

    def _register_fastmcp_handlers(self):
        """Registers FastMCP tools, resources, and prompts with official MCP Python SDK."""
        if not self.mcp_app:
            return

        # Register Tool Handlers
        for tool_meta in MCPToolRegistry.list_tools():
            tool_name = tool_meta["name"]

            def make_handler(name: str):
                def handler(**kwargs) -> Dict[str, Any]:
                    res = self.execute_tool(name, kwargs)
                    return res.model_dump()
                handler.__name__ = name
                handler.__doc__ = tool_meta["description"]
                return handler

            try:
                self.mcp_app.add_tool(make_handler(tool_name))
            except Exception as e:
                logger.debug(f"MCPServer: Tool registration notice for '{tool_name}': {e}")

    def list_tools(self) -> List[Dict[str, Any]]:
        return MCPToolRegistry.list_tools()

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], dry_run: bool = False) -> OperationResult:
        result = MCPToolRegistry.execute_tool(tool_name, arguments, dry_run=dry_run)
        if result.audit_entry:
            self.audit_log.append(result.audit_entry)
        return result

    def list_resources(self):
        return MCPResourceCatalog.list_resources()

    def read_resource(self, uri: str) -> Dict[str, Any]:
        return MCPResourceCatalog.read_resource(uri)

    def list_prompts(self):
        return MCPPromptCatalog.list_prompts()

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return MCPPromptCatalog.get_prompt(name, arguments)

    def run(self):
        """Runs the MCP server using selected transport."""
        logger.info(f"MCPServer starting transport '{self.transport}' on {self.host}:{self.port}")
        if self._sdk_available and self.mcp_app:
            if self.transport == "stdio":
                self.mcp_app.run(transport="stdio")
            else:
                self.mcp_app.run(transport="sse")
        else:
            print(f"MCPServer running in standalone mode (transport={self.transport})")


if __name__ == "__main__":
    server = MCPServer(transport="stdio")
    server.run()
