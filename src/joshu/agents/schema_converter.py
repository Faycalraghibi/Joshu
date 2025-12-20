"""
JSON Schema Conversion Utilities for Agent Definitions.

This module provides utilities to convert InputConfig and OutputConfig
definitions into valid JSON Schema objects for:
- Validating agent invocations
- Exposing agent inputs to LLMs
- Tool parameter validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from joshu.agents.definitions import FieldDefinition, InputConfig, OutputConfig
from joshu.agents.exceptions import SchemaConversionError

logger = logging.getLogger(__name__)

# Type mapping from field_type to JSON Schema type
TYPE_MAPPING = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


def field_to_json_schema(field: FieldDefinition) -> Dict[str, Any]:
    """
    Convert a single FieldDefinition to a JSON Schema property definition.

    Args:
        field: The field definition to convert

    Returns:
        JSON Schema property definition

    Raises:
        SchemaConversionError: If the field type is not supported
    """
    if field.field_type not in TYPE_MAPPING:
        raise SchemaConversionError(
            f"Unsupported field type '{field.field_type}' for field '{field.name}'"
        )

    schema: Dict[str, Any] = {
        "type": TYPE_MAPPING[field.field_type],
    }

    # Add description if present
    if field.description:
        schema["description"] = field.description

    # Add default if present and field is optional
    if not field.required and field.default is not None:
        schema["default"] = field.default

    # Handle array items
    if field.field_type == "array":
        if field.items_type:
            if field.items_type not in TYPE_MAPPING:
                raise SchemaConversionError(
                    f"Unsupported items_type '{field.items_type}' for array field '{field.name}'"
                )
            # If items_type is 'object' and we have nested properties
            if field.items_type == "object" and field.properties:
                schema["items"] = _build_object_schema(field.properties)
            else:
                schema["items"] = {"type": TYPE_MAPPING[field.items_type]}
        else:
            # Default to any type if items_type not specified
            schema["items"] = {}

    # Handle nested object properties
    if field.field_type == "object" and field.properties:
        nested_schema = _build_object_schema(field.properties)
        schema["properties"] = nested_schema["properties"]
        if "required" in nested_schema and nested_schema["required"]:
            schema["required"] = nested_schema["required"]

    return schema


def _build_object_schema(fields: List[FieldDefinition]) -> Dict[str, Any]:
    """
    Build a JSON Schema object definition from a list of field definitions.

    Args:
        fields: List of field definitions

    Returns:
        JSON Schema object definition with properties and required fields
    """
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for field in fields:
        properties[field.name] = field_to_json_schema(field)
        if field.required:
            required.append(field.name)

    result: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required:
        result["required"] = required

    return result


def input_config_to_json_schema(config: InputConfig) -> Dict[str, Any]:
    """
    Convert an InputConfig to a valid JSON Schema object.

    This produces a deterministic JSON Schema suitable for:
    - Validating agent invocations
    - Exposing agent inputs to LLMs
    - Tool parameter validation

    Args:
        config: The InputConfig to convert

    Returns:
        Valid JSON Schema object

    Raises:
        SchemaConversionError: If conversion fails due to unsupported types

    Example:
        >>> config = InputConfig(fields=[
        ...     FieldDefinition(name="query", field_type="string", required=True),
        ...     FieldDefinition(name="limit", field_type="integer", required=False, default=10),
        ... ])
        >>> schema = input_config_to_json_schema(config)
        >>> schema
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    """
    if not config.fields:
        return {
            "type": "object",
            "properties": {},
        }

    return _build_object_schema(config.fields)


def output_config_to_json_schema(config: OutputConfig) -> Dict[str, Any]:
    """
    Convert an OutputConfig to a valid JSON Schema object.

    This produces a deterministic JSON Schema suitable for
    validating agent output responses.

    Args:
        config: The OutputConfig to convert

    Returns:
        Valid JSON Schema object

    Raises:
        SchemaConversionError: If conversion fails due to unsupported types
    """
    if not config.fields:
        return {
            "type": "object",
            "properties": {},
        }

    return _build_object_schema(config.fields)
