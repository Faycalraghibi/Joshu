# Test Alignment Fixes

## Summary
This document tracks test fixes needed after the storage refactoring and codebase changes.

## Issues Found

### 1. ✅ Fixed: `test_context_provider.py`
- **Issue**: Uses `memory_store.kv` which was removed during refactoring
- **Status**: Fixed - Added `@property kv` to `MemoryStore` for backward compatibility
- **Tests affected**: 
  - `test_context_provider_initialization`
  - `test_context_provider_clear_context`
  - `test_context_provider_get_context_summary`

### 2. ⚠️ Needs Fix: `test_history_commands.py`
- **Issue**: Uses `src.joshu.ui.cli.context_provider` which is a global variable
- **Current behavior**: The CLI handlers now accept `context_provider` as a parameter
- **Tests affected**: All history-related tests
- **Fix needed**: Update mocks to work with the new handler pattern

### 3. ✅ No issues: `test_memory_summary.py`
- **Status**: Should work correctly as it doesn't directly access storage internals

### 4. ✅ Storage abstraction
- **Status**: All tests should work with JSON storage backend as it's transparent

## Files to Update

1. `tests/test_history_commands.py` - Update mocking strategy for CLI handlers

