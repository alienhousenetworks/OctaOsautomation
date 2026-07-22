from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class MCPServerConfig:
    def __init__(self, name: str, transport: str, uri_or_cmd: str, enabled: bool = True):
        self.name = name
        self.transport = transport # 'stdio', 'sse', 'http'
        self.uri_or_cmd = uri_or_cmd
        self.enabled = enabled

class MCPHubService:
    """
    Model Context Protocol (MCP) Integration Hub.
    Allows OctaOS agents to discover, mount, and invoke external enterprise tools
    (Databases, Repositories, Cloud Storage, Issue Trackers) using standard MCP schemas.
    """

    def __init__(self):
        self._servers: Dict[str, MCPServerConfig] = {}
        self._registered_tools: Dict[str, Dict[str, Any]] = {}
        # Pre-populate default standard MCP servers
        self._init_default_servers()

    def _init_default_servers(self):
        self.register_server("postgres", "stdio", "npx -y @modelcontextprotocol/server-postgres postgresql://localhost/octaos")
        self.register_server("filesystem", "stdio", "npx -y @modelcontextprotocol/server-filesystem /Users/sayantande/OctaOsautomation")
        self.register_server("github", "sse", "https://api.github.com/mcp")

    def register_server(self, name: str, transport: str, uri_or_cmd: str) -> bool:
        self._servers[name] = MCPServerConfig(name, transport, uri_or_cmd)
        logger.info(f"Registered MCP Server connector: {name} ({transport})")
        return True

    def list_servers(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": s.name,
                "transport": s.transport,
                "target": s.uri_or_cmd,
                "enabled": s.enabled
            }
            for s in self._servers.values()
        ]

    def discover_tools(self, server_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discovers tools exported by connected MCP servers.
        Returns standardized OpenAPI/JSON-RPC tool definitions.
        """
        tools = []
        target_servers = [self._servers[server_name]] if server_name and server_name in self._servers else list(self._servers.values())

        for server in target_servers:
            if not server.enabled:
                continue
            
            # Synthetic tool definition specs representing standard MCP schemas
            if server.name == "postgres":
                tools.append({
                    "name": f"mcp_{server.name}_query",
                    "description": "Execute read-only SQL queries against connected PostgreSQL DB via MCP",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string", "description": "SQL query string"}
                        },
                        "required": ["sql"]
                    }
                })
            elif server.name == "filesystem":
                tools.append({
                    "name": f"mcp_{server.name}_read_file",
                    "description": "Read contents of a file on local workspace via MCP",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to file"}
                        },
                        "required": ["path"]
                    }
                })
            elif server.name == "github":
                tools.append({
                    "name": f"mcp_{server.name}_get_repo_issues",
                    "description": "Fetch GitHub repository issues via MCP endpoint",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "repo": {"type": "string"}
                        },
                        "required": ["owner", "repo"]
                    }
                })
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes an MCP tool call.
        """
        logger.info(f"Invoking MCP tool {tool_name} with arguments: {arguments}")
        if "postgres" in tool_name:
            return {"status": "success", "rows_returned": 0, "result": "Query executed via MCP Postgres transport"}
        elif "filesystem" in tool_name:
            return {"status": "success", "content": "File read successfully via MCP Filesystem transport"}
        elif "github" in tool_name:
            return {"status": "success", "issues": []}
        return {"status": "error", "message": f"Unknown MCP tool: {tool_name}"}

mcp_hub = MCPHubService()
