from __future__ import annotations

from typing import Any

from .client import MCPClient
from .models import MCPToolPolicy
from ..core.models import ToolCall, ToolExecutionResult, ToolSpec


class MCPToolArgumentValidationError(ValueError):
    pass


class MCPToolRegistry:
    def __init__(
        self,
        client: MCPClient,
        *,
        default_policy: MCPToolPolicy | None = None,
        tool_policies: dict[str, MCPToolPolicy] | None = None,
    ) -> None:
        self.client = client
        self.default_policy = default_policy or MCPToolPolicy()
        self.tool_policies = dict(tool_policies or {})

    def build_tool_specs(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for tool in self.client.list_tools():
            policy = self.tool_policies.get(tool.name, self.default_policy)
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=policy.description or tool.description or f"MCP tool '{tool.name}'.",
                    sensitive=policy.sensitive,
                    requires_human_approval=policy.requires_human_approval,
                    max_risk_score=policy.max_risk_score,
                )
            )
        return specs


class MCPToolExecutor:
    def __init__(self, client: MCPClient, *, server_name: str = "mcp") -> None:
        self.client = client
        self.server_name = server_name
        self._tool_schemas: dict[str, dict[str, Any]] | None = None

    def validate(self, tool_call: ToolCall) -> list[str]:
        try:
            schema = self._tool_schema(tool_call.name)
        except Exception as exc:
            return [
                (
                    f"Nao foi possivel carregar o schema MCP de '{tool_call.name}' "
                    f"({exc.__class__.__name__})."
                )
            ]

        if not schema:
            return []

        return _validate_schema(
            dict(tool_call.arguments),
            schema,
            path=f"tool_call.arguments.{tool_call.name}",
        )

    def execute(self, tool_call: ToolCall) -> ToolExecutionResult:
        validation_errors = self.validate(tool_call)
        if validation_errors:
            raise MCPToolArgumentValidationError("; ".join(validation_errors))

        result = self.client.call_tool(tool_call.name, tool_call.arguments)
        output = {
            "content": [dict(item) for item in result.content],
            "structured_content": result.structured_content,
            "text": result.text_content(),
        }
        return ToolExecutionResult(
            tool_name=tool_call.name,
            arguments=dict(tool_call.arguments),
            success=not result.is_error,
            output=output,
            metadata={
                "executor": "mcp",
                "server_name": self.server_name,
                **dict(result.metadata),
            },
        )

    def _tool_schema(self, tool_name: str) -> dict[str, Any]:
        if self._tool_schemas is None:
            self._tool_schemas = {
                tool.name: dict(tool.input_schema)
                for tool in self.client.list_tools()
            }
        return dict(self._tool_schemas.get(tool_name, {}))


def _validate_schema(value: Any, schema: dict[str, Any], *, path: str) -> list[str]:
    if not schema:
        return []

    errors: list[str] = []
    declared_type = schema.get("type")
    if declared_type and not _matches_declared_type(value, declared_type):
        expected = _type_label(declared_type)
        actual = type(value).__name__
        return [f"{path} deveria ser do tipo {expected}, mas recebeu {actual}."]

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(f"{path} precisa estar dentro do enum permitido.")

    if isinstance(value, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            required = schema.get("required", [])
            if isinstance(required, list):
                for key in required:
                    if key not in value:
                        errors.append(f"{path}.{key} e obrigatorio.")

            for key, nested_schema in properties.items():
                if key in value and isinstance(nested_schema, dict):
                    errors.extend(
                        _validate_schema(
                            value[key],
                            nested_schema,
                            path=f"{path}.{key}",
                        )
                    )

        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            unexpected_keys = sorted(set(value) - set(properties))
            for key in unexpected_keys:
                errors.append(f"{path}.{key} nao e permitido pelo input schema.")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path} precisa ter ao menos {min_items} item(ns).")

        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f"{path} excede o maximo de {max_items} item(ns).")

        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_schema(
                        item,
                        item_schema,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path} precisa ter pelo menos {min_length} caractere(s).")

        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            errors.append(f"{path} excede o maximo de {max_length} caractere(s).")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path} precisa ser maior ou igual a {minimum}.")

        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path} precisa ser menor ou igual a {maximum}.")

    return errors


def _matches_declared_type(value: Any, declared_type: Any) -> bool:
    if isinstance(declared_type, list):
        return any(_matches_declared_type(value, item) for item in declared_type)

    if declared_type == "object":
        return isinstance(value, dict)
    if declared_type == "array":
        return isinstance(value, list)
    if declared_type == "string":
        return isinstance(value, str)
    if declared_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared_type == "boolean":
        return isinstance(value, bool)
    if declared_type == "null":
        return value is None
    return True


def _type_label(declared_type: Any) -> str:
    if isinstance(declared_type, list):
        return " ou ".join(str(item) for item in declared_type)
    return str(declared_type)
