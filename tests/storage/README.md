# Storage Tests

This directory contains all storage-related tests for the Joshu Assistant project.

## Organization

- `test_storage_system.py` - Core storage system tests for JsonFileStorage
- `test_context_provider_storage_integration.py` - Context provider storage integration tests

## Refactored Tests

The following tests were moved from other test files to this directory:

1. Storage-related tests from `test_context_provider.py`
2. Storage-related tests from `test_context_integration.py`

The original test files have been updated to:
- Remove storage-related tests
- Add notes indicating where the storage tests have been moved
- Use temporary storage or mocks where needed to avoid interference from existing data

## Test Structure

All tests use temporary directories and files to ensure isolation and prevent interference between test runs.
