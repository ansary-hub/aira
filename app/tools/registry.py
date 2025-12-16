import logging
from typing import Any

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry that manages all available tools for the agent."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name.

        Args:
            name: Name of the tool to unregister

        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_all_schemas(self) -> list[dict]:
        """Get schemas for all registered tools (for LLM function calling).

        Returns:
            List of tool schemas
        """
        return [tool.get_schema() for tool in self._tools.values()]

    def get_tools_description(self) -> str:
        """Get a formatted description of all tools for prompt injection.

        Returns:
            Formatted string describing all available tools
        """
        descriptions = []
        for tool in self._tools.values():
            params = tool._get_parameters_schema()
            param_desc = []
            for name, info in params.get("properties", {}).items():
                required = name in params.get("required", [])
                req_str = "(required)" if required else "(optional)"
                param_desc.append(f"    - {name} {req_str}: {info.get('description', 'No description')}")

            descriptions.append(
                f"- {tool.name}: {tool.description}\n"
                f"  Parameters:\n" + "\n".join(param_desc)
            )
        return "\n\n".join(descriptions)

    async def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name with given parameters.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters to pass to the tool

        Returns:
            ToolResult from the tool execution
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found. Available tools: {', '.join(self.list_tools())}",
            )

        try:
            logger.info(f"Executing tool: {tool_name} with params: {kwargs}")
            result = await tool.execute(**kwargs)
            logger.info(f"Tool {tool_name} completed: success={result.success}")
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Global registry instance
tool_registry = ToolRegistry()


def register_all_tools() -> None:
    """Register all available tools in the registry."""
    from app.tools.ticker_extractor import ticker_extractor_tool
    from app.tools.news_retriever import news_retriever_tool
    from app.tools.sentiment_analyzer import sentiment_analyzer_tool
    from app.tools.finData_fetcher import findata_fetcher_tool

    tool_registry.register(ticker_extractor_tool)
    tool_registry.register(news_retriever_tool)
    tool_registry.register(sentiment_analyzer_tool)
    tool_registry.register(findata_fetcher_tool)

    logger.info(f"Registered {len(tool_registry)} tools: {tool_registry.list_tools()}")


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance.

    Returns:
        The global ToolRegistry instance
    """
    return tool_registry
