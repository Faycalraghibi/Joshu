#!/usr/bin/env python3
"""
telemetry_utils.py - Shared telemetry helper functions.

Purpose:
    Provides utility functions for telemetry instrumentation
    that can be used by other scripts and the main application.

This module is designed to be imported, not run directly.

Safety Considerations:
    - All functions are no-ops when telemetry is disabled
    - No data is collected without explicit opt-in
"""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Telemetry configuration path
TELEMETRY_CONFIG_PATH = Path.home() / ".joshu" / "telemetry.json"


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled."""
    # Environment variable override
    env_value = os.environ.get("JOSHU_TELEMETRY_ENABLED")
    if env_value is not None:
        return env_value.lower() in ("1", "true", "yes")

    # Check config file
    if not TELEMETRY_CONFIG_PATH.exists():
        return False

    try:
        config = json.loads(TELEMETRY_CONFIG_PATH.read_text())
        return config.get("enabled", False)
    except Exception:
        return False


def get_telemetry_endpoint() -> Optional[str]:
    """Get the configured OTLP endpoint."""
    if not TELEMETRY_CONFIG_PATH.exists():
        return None

    try:
        config = json.loads(TELEMETRY_CONFIG_PATH.read_text())
        return config.get("endpoint")
    except Exception:
        return None


def get_service_name() -> str:
    """Get the service name for telemetry."""
    return os.environ.get("JOSHU_SERVICE_NAME", "joshu-cli")


def create_span_attributes(
    operation: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create standard span attributes."""
    attrs = {
        "operation": operation,
        "service.name": get_service_name(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    attrs.update(kwargs)
    return attrs


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for tracing operations.

    When telemetry is disabled, this is a no-op.
    When enabled, it creates a span for the operation.

    Usage:
        with trace_operation("build_package", {"package": "joshu"}):
            # do work
            pass
    """
    if not is_telemetry_enabled():
        yield
        return

    # When telemetry is enabled, we would use OpenTelemetry here
    # For now, just provide timing information
    start_time = datetime.now(timezone.utc)

    try:
        yield
    finally:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Log trace information (placeholder for actual OTLP export)
        trace_data = {
            "operation": operation_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "attributes": attributes or {},
        }

        # In a real implementation, this would export to OTLP
        # For debugging, we can print if verbose mode is on
        if os.environ.get("JOSHU_TELEMETRY_DEBUG"):
            print(f"[trace] {json.dumps(trace_data)}")


def record_metric(
    name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """
    Record a metric value.

    No-op when telemetry is disabled.
    """
    if not is_telemetry_enabled():
        return

    metric_data = {
        "name": name,
        "value": value,
        "labels": labels or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if os.environ.get("JOSHU_TELEMETRY_DEBUG"):
        print(f"[metric] {json.dumps(metric_data)}")


def record_event(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record an event.

    No-op when telemetry is disabled.
    """
    if not is_telemetry_enabled():
        return

    event_data = {
        "name": name,
        "attributes": attributes or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if os.environ.get("JOSHU_TELEMETRY_DEBUG"):
        print(f"[event] {json.dumps(event_data)}")


# Example usage in docstring
__doc__ += """

Example Usage:
    from scripts.telemetry_utils import trace_operation, record_metric

    with trace_operation("build", {"package": "joshu"}):
        # Build logic here
        record_metric("build_duration", 12.5)
"""
