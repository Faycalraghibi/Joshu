"""
Unit tests for JSON Schema conversion utilities.

Run with: pytest tests/agents/test_schema_converter.py -v
"""

import pytest

from joshu.agents.definitions import FieldDefinition, InputConfig, OutputConfig
from joshu.agents.exceptions import SchemaConversionError
from joshu.agents.schema_converter import (
    field_to_json_schema,
    input_config_to_json_schema,
    output_config_to_json_schema,
)


class TestFieldToJsonSchema:
    """Test field_to_json_schema function."""

    def test_string_field(self):
        """Test string field conversion."""
        field = FieldDefinition(name="query", field_type="string", description="Search query")
        schema = field_to_json_schema(field)
        assert schema["type"] == "string"
        assert schema["description"] == "Search query"

    def test_integer_field(self):
        """Test integer field conversion."""
        field = FieldDefinition(name="count", field_type="integer")
        schema = field_to_json_schema(field)
        assert schema["type"] == "integer"

    def test_number_field(self):
        """Test number field conversion."""
        field = FieldDefinition(name="price", field_type="number")
        schema = field_to_json_schema(field)
        assert schema["type"] == "number"

    def test_boolean_field(self):
        """Test boolean field conversion."""
        field = FieldDefinition(name="active", field_type="boolean")
        schema = field_to_json_schema(field)
        assert schema["type"] == "boolean"

    def test_optional_field_with_default(self):
        """Test optional field includes default."""
        field = FieldDefinition(name="limit", field_type="integer", required=False, default=10)
        schema = field_to_json_schema(field)
        assert schema["type"] == "integer"
        assert schema["default"] == 10

    def test_required_field_no_default(self):
        """Test required field does not include default."""
        field = FieldDefinition(name="limit", field_type="integer", required=True, default=10)
        schema = field_to_json_schema(field)
        assert "default" not in schema

    def test_field_without_description(self):
        """Test field without description."""
        field = FieldDefinition(name="query", field_type="string")
        schema = field_to_json_schema(field)
        assert "description" not in schema

    def test_unsupported_type_raises_error(self):
        """Test unsupported type raises SchemaConversionError."""
        field = FieldDefinition(name="bad", field_type="unsupported")
        with pytest.raises(SchemaConversionError) as exc_info:
            field_to_json_schema(field)
        assert "Unsupported field type" in str(exc_info.value)


class TestArrayFieldConversion:
    """Test array field conversion to JSON Schema."""

    def test_array_with_string_items(self):
        """Test array with string items type."""
        field = FieldDefinition(name="tags", field_type="array", items_type="string")
        schema = field_to_json_schema(field)
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

    def test_array_with_integer_items(self):
        """Test array with integer items type."""
        field = FieldDefinition(name="ids", field_type="array", items_type="integer")
        schema = field_to_json_schema(field)
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "integer"

    def test_array_without_items_type(self):
        """Test array without items type defaults to empty schema."""
        field = FieldDefinition(name="data", field_type="array")
        schema = field_to_json_schema(field)
        assert schema["type"] == "array"
        assert schema["items"] == {}

    def test_array_with_invalid_items_type(self):
        """Test array with invalid items type raises error."""
        field = FieldDefinition(name="data", field_type="array", items_type="invalid")
        with pytest.raises(SchemaConversionError) as exc_info:
            field_to_json_schema(field)
        assert "Unsupported items_type" in str(exc_info.value)

    def test_array_with_object_items(self):
        """Test array with nested object items."""
        field = FieldDefinition(
            name="users",
            field_type="array",
            items_type="object",
            properties=[
                FieldDefinition(name="name", field_type="string"),
                FieldDefinition(name="age", field_type="integer"),
            ],
        )
        schema = field_to_json_schema(field)
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "object"
        assert "name" in schema["items"]["properties"]
        assert "age" in schema["items"]["properties"]


class TestNestedObjectConversion:
    """Test nested object conversion to JSON Schema."""

    def test_simple_nested_object(self):
        """Test simple nested object conversion."""
        field = FieldDefinition(
            name="user",
            field_type="object",
            properties=[
                FieldDefinition(name="name", field_type="string"),
                FieldDefinition(name="email", field_type="string"),
            ],
        )
        schema = field_to_json_schema(field)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["email"]["type"] == "string"

    def test_nested_object_with_required_fields(self):
        """Test nested object includes required fields."""
        field = FieldDefinition(
            name="user",
            field_type="object",
            properties=[
                FieldDefinition(name="name", field_type="string", required=True),
                FieldDefinition(name="nickname", field_type="string", required=False),
            ],
        )
        schema = field_to_json_schema(field)
        assert "required" in schema
        assert "name" in schema["required"]
        assert "nickname" not in schema["required"]

    def test_deeply_nested_object(self):
        """Test deeply nested object conversion."""
        address = FieldDefinition(
            name="address",
            field_type="object",
            properties=[
                FieldDefinition(name="street", field_type="string"),
                FieldDefinition(name="city", field_type="string"),
            ],
        )
        user = FieldDefinition(
            name="user",
            field_type="object",
            properties=[
                FieldDefinition(name="name", field_type="string"),
                address,
            ],
        )
        schema = field_to_json_schema(user)
        assert schema["type"] == "object"
        assert schema["properties"]["address"]["type"] == "object"
        assert "street" in schema["properties"]["address"]["properties"]


class TestInputConfigToJsonSchema:
    """Test input_config_to_json_schema function."""

    def test_empty_config(self):
        """Test empty InputConfig produces valid schema."""
        config = InputConfig(fields=[])
        schema = input_config_to_json_schema(config)
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    def test_simple_config(self):
        """Test simple InputConfig conversion."""
        config = InputConfig(
            fields=[
                FieldDefinition(name="query", field_type="string", required=True),
                FieldDefinition(name="limit", field_type="integer", required=False, default=10),
            ]
        )
        schema = input_config_to_json_schema(config)

        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"
        assert schema["properties"]["limit"]["type"] == "integer"
        assert schema["properties"]["limit"]["default"] == 10
        assert "required" in schema
        assert "query" in schema["required"]
        assert "limit" not in schema["required"]

    def test_all_optional_fields(self):
        """Test config with all optional fields has no required array."""
        config = InputConfig(
            fields=[
                FieldDefinition(name="a", field_type="string", required=False),
                FieldDefinition(name="b", field_type="string", required=False),
            ]
        )
        schema = input_config_to_json_schema(config)
        assert "required" not in schema or len(schema.get("required", [])) == 0

    def test_complex_config(self):
        """Test complex InputConfig with nested objects and arrays."""
        config = InputConfig(
            fields=[
                FieldDefinition(name="query", field_type="string"),
                FieldDefinition(name="tags", field_type="array", items_type="string"),
                FieldDefinition(
                    name="options",
                    field_type="object",
                    properties=[
                        FieldDefinition(name="page", field_type="integer"),
                        FieldDefinition(name="sort", field_type="string"),
                    ],
                ),
            ]
        )
        schema = input_config_to_json_schema(config)

        assert "query" in schema["properties"]
        assert "tags" in schema["properties"]
        assert schema["properties"]["tags"]["type"] == "array"
        assert "options" in schema["properties"]
        assert schema["properties"]["options"]["type"] == "object"


class TestOutputConfigToJsonSchema:
    """Test output_config_to_json_schema function."""

    def test_empty_config(self):
        """Test empty OutputConfig produces valid schema."""
        config = OutputConfig(fields=[])
        schema = output_config_to_json_schema(config)
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    def test_simple_config(self):
        """Test simple OutputConfig conversion."""
        config = OutputConfig(
            fields=[
                FieldDefinition(name="result", field_type="string"),
                FieldDefinition(name="count", field_type="integer"),
            ]
        )
        schema = output_config_to_json_schema(config)

        assert schema["type"] == "object"
        assert "result" in schema["properties"]
        assert "count" in schema["properties"]


class TestDeterministicOutput:
    """Test that schema output is deterministic."""

    def test_same_config_same_output(self):
        """Test same config produces identical output."""
        config = InputConfig(
            fields=[
                FieldDefinition(name="a", field_type="string"),
                FieldDefinition(name="b", field_type="integer"),
            ]
        )
        schema1 = input_config_to_json_schema(config)
        schema2 = input_config_to_json_schema(config)
        assert schema1 == schema2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
