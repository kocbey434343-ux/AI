"""
JSON Schemas for structured log event validation - CR-0075
"""

from typing import Any, Dict

# Common patterns
SYMBOL_PATTERN = r"^[A-Z0-9]+USDT?$"

# Base schema - all events must conform to this
BASE_EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "ts": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"},
        "event": {"type": "string", "minLength": 1}
    },
    "required": ["ts", "event"],
    "additionalProperties": True
}

# Trade & Position Events
TRADE_EVENTS_SCHEMA = {
    "trade_open": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["trade_open"]},
            "symbol": {"type": "string", "pattern": SYMBOL_PATTERN},
            "trade_id": {"type": "string"},
            "entry_price": {"type": "number", "minimum": 0},
            "position_size": {"type": "number", "minimum": 0},
            "side": {"enum": ["BUY", "SELL"]}
        },
        "required": ["ts", "event", "symbol", "trade_id"],
        "additionalProperties": True
    },
    "trade_close": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["trade_close"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "trade_id": {"type": "string"},
            "realized_pnl": {"type": "number"},
            "exit_price": {"type": "number", "minimum": 0}
        },
        "required": ["ts", "event", "symbol", "trade_id"],
        "additionalProperties": True
    },
    "partial_exit": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["partial_exit"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "qty": {"type": "number", "minimum": 0},
            "remaining_size": {"type": "number", "minimum": 0},
            "r_multiple": {"type": "number"}
        },
        "required": ["ts", "event", "symbol", "qty"],
        "additionalProperties": True
    }
}

# Auto-heal Events
HEALING_EVENTS_SCHEMA = {
    "auto_heal_attempt": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["auto_heal_attempt"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"}
        },
        "required": ["ts", "event", "symbol"],
        "additionalProperties": True
    },
    "auto_heal_success": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["auto_heal_success"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "ids": {"type": "array", "items": {"type": "string"}},
            "sl_id": {"type": "string"},
            "tp_id": {"type": "string"},
            "mode": {"enum": ["spot", "futures", "sim"]}
        },
        "required": ["ts", "event", "symbol"],
        "additionalProperties": True
    },
    "auto_heal_fail": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["auto_heal_fail"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "reason": {"type": "string"},
            "error": {"type": "string"},
            "mode": {"enum": ["spot", "futures", "sim"]}
        },
        "required": ["ts", "event", "symbol"],
        "additionalProperties": True
    }
}

# System Events
SYSTEM_EVENTS_SCHEMA = {
    "app_start": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["app_start"]},
            "version": {"type": "string"},
            "offline": {"type": "boolean"}
        },
        "required": ["ts", "event"],
        "additionalProperties": True
    },
    "shutdown_snapshot": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["shutdown_snapshot"]},
            "positions": {"type": "integer", "minimum": 0},
            "counters": {"type": "integer", "minimum": 0}
        },
        "required": ["ts", "event"],
        "additionalProperties": True
    },
    "daily_risk_reset": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["daily_risk_reset"]},
            "previous": {"type": "string"},
            "current": {"type": "string"},
            "cleared": {"type": "integer", "minimum": 0}
        },
        "required": ["ts", "event"],
        "additionalProperties": True
    },
    "reconciliation": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["reconciliation"]},
            "duration_s": {"type": "number", "minimum": 0},
            "orphan_exchange_positions": {"type": "integer", "minimum": 0},
            "orphan_exchange_orders": {"type": "integer", "minimum": 0},
            "orphan_local_positions": {"type": "integer", "minimum": 0}
        },
        "required": ["ts", "event"],
        "additionalProperties": True
    }
}

# Guard Events
GUARD_EVENTS_SCHEMA = {
    "lookahead_prevention": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["lookahead_prevention"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "reason": {"type": "string"}
        },
        "required": ["ts", "event", "symbol", "reason"],
        "additionalProperties": True
    },
    "lookahead_violation": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["lookahead_violation"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "reason": {"type": "string"},
            "severity": {"enum": ["INFO", "WARNING", "ERROR"]}
        },
        "required": ["ts", "event", "symbol", "reason"],
        "additionalProperties": True
    },
    "signal_blocked": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["signal_blocked"]},
            "symbol": {"type": "string", "pattern": r"^[A-Z0-9]+USDT?$"},
            "reason": {"type": "string"}
        },
        "required": ["ts", "event", "symbol", "reason"],
        "additionalProperties": True
    },
    "slippage_guard_error": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["slippage_guard_error"]},
            "error": {"type": "string"},
            "context": {"type": "object"}
        },
        "required": ["ts", "event", "error"],
        "additionalProperties": True
    },
    "correlation_adjust": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["correlation_adjust"]},
            "action": {"enum": ["ease", "tighten"]},
            "value": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["ts", "event", "action", "value"],
        "additionalProperties": True
    }
}

# Exception Events
EXCEPTION_EVENTS_SCHEMA = {
    "exception_capture": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["exception_capture"]},
            "scope": {"type": "string"},
            "error": {"type": "string"}
        },
        "required": ["ts", "event", "scope", "error"],
        "additionalProperties": True
    },
    "exception_hook_installed": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["exception_hook_installed"]}
        },
        "required": ["ts", "event"],
        "additionalProperties": True
    }
}

# Headless Runner Events
HEADLESS_EVENTS_SCHEMA = {
    "headless_runner_init": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["headless_runner_init"]},
            "mode": {"enum": ["headless", "daemon"]},
            "pid": {"type": "integer", "minimum": 1}
        },
        "required": ["ts", "event", "mode", "pid"],
        "additionalProperties": True
    },
    "component_initialized": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["component_initialized"]},
            "component": {"type": "string"},
            "entries": {"type": "integer"},
            "offline_mode": {"type": "boolean"}
        },
        "required": ["ts", "event", "component"],
        "additionalProperties": True
    },
    "environment_validation_failed": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["environment_validation_failed"]},
            "problems": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["ts", "event", "problems"],
        "additionalProperties": True
    },
    "degraded_mode_activated": {
        "type": "object",
        "properties": {
            "ts": {"type": "string"},
            "event": {"enum": ["degraded_mode_activated"]},
            "reason": {"type": "string"}
        },
        "required": ["ts", "event", "reason"],
        "additionalProperties": True
    }
}

# Combined schema dictionary
ALL_EVENT_SCHEMAS: Dict[str, Dict[str, Any]] = {}
ALL_EVENT_SCHEMAS.update(TRADE_EVENTS_SCHEMA)
ALL_EVENT_SCHEMAS.update(HEALING_EVENTS_SCHEMA)
ALL_EVENT_SCHEMAS.update(SYSTEM_EVENTS_SCHEMA)
ALL_EVENT_SCHEMAS.update(GUARD_EVENTS_SCHEMA)
ALL_EVENT_SCHEMAS.update(EXCEPTION_EVENTS_SCHEMA)
ALL_EVENT_SCHEMAS.update(HEADLESS_EVENTS_SCHEMA)

def get_schema_for_event(event_name: str) -> Dict[str, Any]:
    """Get JSON schema for specific event type."""
    return ALL_EVENT_SCHEMAS.get(event_name, BASE_EVENT_SCHEMA)

def get_all_supported_events() -> list[str]:
    """Get list of all supported event names."""
    return list(ALL_EVENT_SCHEMAS.keys())
