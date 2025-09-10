"""
JSON Schema validator for structured log events - CR-0075
"""

from typing import Any, Dict

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


# Common patterns
SYMBOL_PATTERN = r"^[A-Z0-9]+USDT?$"

# Base schema for all events
BASE_SCHEMA = {
    "type": "object",
    "properties": {
        "ts": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"},
        "event": {"type": "string", "minLength": 1}
    },
    "required": ["ts", "event"],
    "additionalProperties": True
}

# Event-specific schemas
EVENT_SCHEMAS = {
    # Trade Events
    "trade_open": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "trade_id": {"type": "string"},
            "entry_price": {"type": "number", "minimum": 0},
            "position_size": {"type": "number", "minimum": 0},
            "side": {"enum": ["BUY", "SELL"]}
        },
        "required": ["symbol", "trade_id"]
    },
    "trade_close": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "trade_id": {"type": "string"},
            "realized_pnl": {"type": "number"},
            "exit_price": {"type": "number", "minimum": 0}
        },
        "required": ["symbol", "trade_id"]
    },
    "partial_exit": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "qty": {"type": "number", "minimum": 0},
            "remaining_size": {"type": "number", "minimum": 0},
            "r_multiple": {"type": "number"}
        },
        "required": ["symbol", "qty"]
    },
    # Auto-heal Events
    "auto_heal_attempt": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN}
        },
        "required": ["symbol"]
    },
    "auto_heal_success": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "ids": {"type": "array", "items": {"type": "string"}},
            "sl_id": {"type": "string"},
            "tp_id": {"type": "string"},
            "mode": {"enum": ["spot", "futures", "sim"]}
        },
        "required": ["symbol"]
    },
    "auto_heal_fail": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "reason": {"type": "string"},
            "error": {"type": "string"},
            "mode": {"enum": ["spot", "futures", "sim"]}
        },
        "required": ["symbol"]
    },
    # System Events
    "app_start": {
        "properties": {
            "version": {"type": "string"},
            "offline": {"type": "boolean"}
        }
    },
    "shutdown_snapshot": {
        "properties": {
            "positions": {"type": "integer", "minimum": 0},
            "counters": {"type": "integer", "minimum": 0}
        }
    },
    "daily_risk_reset": {
        "properties": {
            "previous": {"type": "string"},
            "current": {"type": "string"},
            "cleared": {"type": "integer", "minimum": 0}
        }
    },
    "reconciliation": {
        "properties": {
            "duration_s": {"type": "number", "minimum": 0},
            "orphan_exchange_positions": {"type": "integer", "minimum": 0},
            "orphan_exchange_orders": {"type": "integer", "minimum": 0},
            "orphan_local_positions": {"type": "integer", "minimum": 0}
        }
    },
    # Guard Events
    "lookahead_prevention": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "reason": {"type": "string"}
        },
        "required": ["symbol", "reason"]
    },
    "lookahead_violation": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "reason": {"type": "string"},
            "severity": {"enum": ["INFO", "WARNING", "ERROR"]}
        },
        "required": ["symbol", "reason"]
    },
    "signal_blocked": {
        "properties": {
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "reason": {"type": "string"}
        },
        "required": ["symbol", "reason"]
    },
    "slippage_guard_error": {
        "properties": {
            "error": {"type": "string"},
            "context": {"type": "object"}
        },
        "required": ["error"]
    },
    "correlation_adjust": {
        "properties": {
            "action": {"enum": ["ease", "tighten"]},
            "value": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["action", "value"]
    },
    # Exception Events
    "exception_capture": {
        "properties": {
            "scope": {"type": "string"},
            "error": {"type": "string"}
        },
        "required": ["scope", "error"]
    },
    "exception_hook_installed": {
        "properties": {}
    },
    # Headless Runner Events
    "headless_runner_init": {
        "properties": {
            "mode": {"enum": ["headless", "daemon"]},
            "pid": {"type": "integer", "minimum": 1}
        },
        "required": ["mode", "pid"]
    },
    "component_initialized": {
        "properties": {
            "component": {"type": "string"},
            "entries": {"type": "integer"},
            "offline_mode": {"type": "boolean"}
        },
        "required": ["component"]
    },
    "environment_validation_failed": {
        "properties": {
            "problems": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["problems"]
    },
    "degraded_mode_activated": {
        "properties": {
            "reason": {"type": "string"}
        },
        "required": ["reason"]
    }
}


def _merge_schemas(base_schema: Dict[str, Any], event_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Merge base schema with event-specific schema."""
    merged = base_schema.copy()

    # Merge properties
    if "properties" in event_schema:
        merged["properties"].update(event_schema["properties"])

    # Merge required fields
    if "required" in event_schema:
        merged["required"] = list(set(merged["required"] + event_schema["required"]))

    return merged


def get_schema_for_event(event_name: str) -> Dict[str, Any]:
    """Get complete JSON schema for specific event type."""
    if event_name in EVENT_SCHEMAS:
        return _merge_schemas(BASE_SCHEMA, EVENT_SCHEMAS[event_name])
    return BASE_SCHEMA


def validate_event(event_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate structured log event against JSON schema.

    Returns:
        (is_valid, error_message)
    """
    if not JSONSCHEMA_AVAILABLE:
        # Graceful degradation - no validation if jsonschema not available
        return True, ""

    if not isinstance(event_data, dict):
        return False, "Event data must be a dictionary"

    if "event" not in event_data:
        return False, "Missing required field: event"

    event_name = event_data["event"]
    schema = get_schema_for_event(event_name)

    try:
        jsonschema.validate(event_data, schema)
        return True, ""
    except jsonschema.ValidationError as e:
        return False, f"Schema validation failed: {e.message}"
    except Exception as e:
        return False, f"Validation error: {e!s}"


def get_supported_events() -> list[str]:
    """Get list of all supported event names with specific schemas."""
    return list(EVENT_SCHEMAS.keys())


def is_event_supported(event_name: str) -> bool:
    """Check if event has specific schema defined."""
    return event_name in EVENT_SCHEMAS
