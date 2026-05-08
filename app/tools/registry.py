from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ToolExecutionError(Exception):
    pass


class ToolNotFoundError(ToolExecutionError):
    pass


class ToolArgumentError(ToolExecutionError):
    pass


class ToolItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    source_type: str
    summary: str
    url: str | None = None
    published_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_name: str
    query: str
    items: list[ToolItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SearchToolArgs(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class ToolSpec(BaseModel):
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], ToolResult]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        args_model: type[BaseModel],
        handler: Callable[[BaseModel], ToolResult],
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            args_model=args_model,
            handler=handler,
        )

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": spec.name, "description": spec.description}
            for spec in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if not spec:
            raise ToolNotFoundError(f"Tool not found: {name}")

        try:
            parsed_args = spec.args_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentError(str(exc)) from exc

        return spec.handler(parsed_args)
