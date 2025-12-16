from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Result from a tool execution."""

    success: bool
    data: Any = None
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given parameters."""
        pass

    def get_schema(self) -> dict:
        """Get the tool's schema for function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters_schema(),
        }

    @abstractmethod
    def _get_parameters_schema(self) -> dict:
        """Get the JSON schema for the tool's parameters."""
        pass
