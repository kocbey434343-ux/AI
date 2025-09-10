"""
Risk Kill-Switch Escalation System - CR-0076

Unified risk escalation system that coordinates all risk control mechanisms:
- Daily loss limits
- Consecutive loss limits
- Latency/slippage anomalies
- Manual halt flags
- Escalation levels and recovery
"""

from __future__ import annotations

import contextlib
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from config.settings import Settings
from src.utils.structured_log import slog


class RiskLevel(Enum):
    """Risk escalation levels."""
    NORMAL = "normal"
    WARNING = "warning"  # Risk reduction applied
    CRITICAL = "critical"  # Trading halted, positions may be closed
    EMERGENCY = "emergency"  # All positions closed, system halted


class RiskEscalation:
    """Unified risk escalation control system."""

    # Constants
    MAX_HISTORY_SIZE = 100
    HISTORY_TRIM_SIZE = 50

    def __init__(self, trader_instance):
        self.trader = trader_instance
        self.current_level = RiskLevel.NORMAL
        self.escalation_reasons = set()
        self.escalation_history = []
        self._original_risk_percent = None
        self._escalation_start_time = None

        # Thresholds for escalation
        self.LEVEL_THRESHOLDS = {
            RiskLevel.WARNING: {
                "daily_loss_pct": Settings.MAX_DAILY_LOSS_PCT * 0.7,  # 70% of limit
                "consecutive_losses": Settings.MAX_CONSECUTIVE_LOSSES * 0.75,  # 75% of limit
                "latency_ms": Settings.LATENCY_ANOMALY_MS,
                "slippage_bps": Settings.SLIPPAGE_ANOMALY_BPS
            },
            RiskLevel.CRITICAL: {
                "daily_loss_pct": Settings.MAX_DAILY_LOSS_PCT,
                "consecutive_losses": Settings.MAX_CONSECUTIVE_LOSSES,
                "latency_ms": Settings.LATENCY_ANOMALY_MS * 2,
                "slippage_bps": Settings.SLIPPAGE_ANOMALY_BPS * 2
            }
        }

    def evaluate_risk_level(self) -> RiskLevel:
        """Evaluate current risk situation and determine appropriate level."""
        # Check manual halt first
        if self._check_manual_halt():
            return self._escalate_to_level(RiskLevel.CRITICAL, {"manual_halt"})

        # Get current metrics
        risk_metrics = self._get_risk_metrics()
        if not risk_metrics:
            return self.current_level

        # Evaluate risk levels
        risk_level, reasons = self._evaluate_risk_conditions(risk_metrics)
        return self._escalate_to_level(risk_level, reasons)

    def _check_manual_halt(self) -> bool:
        """Check if manual halt flag exists."""
        halt_flag = Path(Settings.DAILY_HALT_FLAG_PATH)
        return halt_flag.exists()

    def _get_risk_metrics(self) -> dict:
        """Get current risk metrics for evaluation."""
        try:
            daily_pnl = self.trader.trade_store.daily_realized_pnl_pct()
            consecutive_losses = self.trader.trade_store.consecutive_losses()
            stats = self._get_recent_performance_stats()

            return {
                'daily_pnl': daily_pnl,
                'consecutive_losses': consecutive_losses,
                'recent_latency': stats.get('avg_latency_ms', 0),
                'recent_slippage': stats.get('avg_slippage_bps', 0)
            }
        except Exception:
            return {}

    def _evaluate_risk_conditions(self, metrics: dict) -> tuple:
        """Evaluate risk conditions and return level and reasons."""
        reasons = set()

        # Check CRITICAL level first
        if self._check_critical_conditions(metrics, reasons):
            return RiskLevel.CRITICAL, reasons

        # Check WARNING level
        if self._check_warning_conditions(metrics, reasons):
            return RiskLevel.WARNING, reasons

        return RiskLevel.NORMAL, reasons

    def _check_critical_conditions(self, metrics: dict, reasons: set) -> bool:
        """Check if any critical conditions are met."""
        critical_thresholds = self.LEVEL_THRESHOLDS[RiskLevel.CRITICAL]
        critical_triggered = False

        if metrics['daily_pnl'] <= -critical_thresholds["daily_loss_pct"]:
            reasons.add("daily_loss_critical")
            critical_triggered = True

        if metrics['consecutive_losses'] >= critical_thresholds["consecutive_losses"]:
            reasons.add("consecutive_losses_critical")
            critical_triggered = True

        if metrics['recent_latency'] > critical_thresholds["latency_ms"]:
            reasons.add("latency_critical")
            critical_triggered = True

        if metrics['recent_slippage'] > critical_thresholds["slippage_bps"]:
            reasons.add("slippage_critical")
            critical_triggered = True

        return critical_triggered

    def _check_warning_conditions(self, metrics: dict, reasons: set) -> bool:
        """Check if any warning conditions are met."""
        warning_thresholds = self.LEVEL_THRESHOLDS[RiskLevel.WARNING]
        warning_triggered = False

        if metrics['daily_pnl'] <= -warning_thresholds["daily_loss_pct"]:
            reasons.add("daily_loss_warning")
            warning_triggered = True

        if metrics['consecutive_losses'] >= warning_thresholds["consecutive_losses"]:
            reasons.add("consecutive_losses_warning")
            warning_triggered = True

        if metrics['recent_latency'] > warning_thresholds["latency_ms"]:
            reasons.add("latency_warning")
            warning_triggered = True

        if metrics['recent_slippage'] > warning_thresholds["slippage_bps"]:
            reasons.add("slippage_warning")
            warning_triggered = True

        return warning_triggered

    def _escalate_to_level(self, new_level: RiskLevel, reasons: set) -> RiskLevel:
        """Escalate to new risk level with appropriate actions."""
        if new_level == self.current_level and reasons == self.escalation_reasons:
            return self.current_level  # No change

        old_level = self.current_level
        self.current_level = new_level
        self.escalation_reasons = reasons

        # Record escalation event
        slog("risk_escalation",
             from_level=old_level.value,
             to_level=new_level.value,
             reasons=list(reasons),
             timestamp=time.time())

        # Apply escalation actions
        if new_level == RiskLevel.WARNING:
            self._apply_warning_actions(reasons)
        elif new_level == RiskLevel.CRITICAL:
            self._apply_critical_actions(reasons)
        elif new_level == RiskLevel.EMERGENCY:
            self._apply_emergency_actions(reasons)
        elif new_level == RiskLevel.NORMAL and old_level != RiskLevel.NORMAL:
            self._apply_recovery_actions()

        # Record in history
        self.escalation_history.append({
            'timestamp': time.time(),
            'from_level': old_level.value,
            'to_level': new_level.value,
            'reasons': list(reasons)
        })

        # Keep history bounded
        if len(self.escalation_history) > self.MAX_HISTORY_SIZE:
            self.escalation_history = self.escalation_history[-self.HISTORY_TRIM_SIZE:]

        return new_level

    def _apply_warning_actions(self, reasons: set):
        """Apply WARNING level risk reduction actions."""
        self.trader.logger.warning(f"Risk escalated to WARNING: {', '.join(reasons)}")

        # Reduce risk percentage
        if self._original_risk_percent is None:
            self._original_risk_percent = self.trader.risk_manager.risk_percent

        self.trader.risk_manager.risk_percent = (
            self._original_risk_percent * Settings.ANOMALY_RISK_MULT
        )

        slog("risk_reduction_applied",
             original_risk=self._original_risk_percent,
             new_risk=self.trader.risk_manager.risk_percent,
             reasons=list(reasons))

        self.trader.logger.info(f"Risk reduced to {self.trader.risk_manager.risk_percent:.3f}%")

    def _apply_critical_actions(self, reasons: set):
        """Apply CRITICAL level halt actions."""
        self.trader.logger.critical(f"Risk escalated to CRITICAL: {', '.join(reasons)}")

        # Create halt flag
        halt_flag = Path(Settings.DAILY_HALT_FLAG_PATH)
        with contextlib.suppress(Exception):
            halt_reason = f"Critical risk escalation: {', '.join(reasons)}"
            halt_flag.write_text(halt_reason)

        # Apply maximum risk reduction
        if self._original_risk_percent is None:
            self._original_risk_percent = self.trader.risk_manager.risk_percent

        # More aggressive risk reduction for critical level
        self.trader.risk_manager.risk_percent = (
            self._original_risk_percent * Settings.ANOMALY_RISK_MULT * 0.5
        )

        slog("risk_halt_applied",
             original_risk=self._original_risk_percent,
             new_risk=self.trader.risk_manager.risk_percent,
             reasons=list(reasons),
             severity="CRITICAL")

        # Record guard events for each reason
        if hasattr(self.trader, 'trade_store') and hasattr(self.trader.trade_store, 'guard_events'):
            for reason in reasons:
                self.trader.trade_store.guard_events.record_guard_event_simple(
                    f"escalation_{reason}", f"Critical risk escalation: {reason}"
                )

    def _apply_emergency_actions(self, reasons: set):
        """Apply EMERGENCY level actions - close all positions."""
        self.trader.logger.critical(f"EMERGENCY risk escalation: {', '.join(reasons)}")

        # Create emergency halt flag
        halt_flag = Path(Settings.DAILY_HALT_FLAG_PATH)
        with contextlib.suppress(Exception):
            emergency_reason = f"EMERGENCY escalation: {', '.join(reasons)}"
            halt_flag.write_text(emergency_reason)

        # Close all positions (if trader supports it)
        if hasattr(self.trader, 'close_all_positions'):
            try:
                self.trader.close_all_positions()
                slog("emergency_close_all", reasons=list(reasons), severity="EMERGENCY")
            except Exception as e:
                self.trader.logger.error(f"Failed to close all positions in emergency: {e}")

        # Zero risk
        if self._original_risk_percent is None:
            self._original_risk_percent = self.trader.risk_manager.risk_percent
        self.trader.risk_manager.risk_percent = 0.0

        slog("emergency_halt", reasons=list(reasons), severity="EMERGENCY")

    def _apply_recovery_actions(self):
        """Apply recovery actions when returning to NORMAL level."""
        self.trader.logger.info("Risk level recovered to NORMAL")

        # Restore original risk percentage
        if self._original_risk_percent is not None:
            self.trader.risk_manager.risk_percent = self._original_risk_percent
            self.trader.logger.info(f"Risk restored to {self.trader.risk_manager.risk_percent:.3f}%")
            self._original_risk_percent = None

        # Clear escalation reasons
        self.escalation_reasons.clear()

        slog("risk_recovery", restored_risk=self.trader.risk_manager.risk_percent)

    def _get_recent_performance_stats(self) -> Dict[str, float]:
        """Get recent performance statistics for escalation evaluation."""
        try:
            if hasattr(self.trader, 'recent_latency_slippage_stats'):
                return self.trader.recent_latency_slippage_stats(window=30)

            # Fallback to direct calculation
            recent_latencies = getattr(self.trader, 'recent_open_latencies', [])
            recent_slippage = getattr(self.trader, 'recent_entry_slippage_bps', [])

            avg_latency = sum(recent_latencies[-30:]) / len(recent_latencies[-30:]) if recent_latencies else 0
            avg_slippage = sum(recent_slippage[-30:]) / len(recent_slippage[-30:]) if recent_slippage else 0

            return {
                'avg_latency_ms': avg_latency,
                'avg_slippage_bps': avg_slippage
            }
        except Exception:
            return {'avg_latency_ms': 0, 'avg_slippage_bps': 0}

    def force_escalation(self, level: RiskLevel, reason: str) -> bool:
        """Manually force escalation to specific level."""
        self.trader.logger.warning(f"Manual risk escalation to {level.value}: {reason}")
        self._escalate_to_level(level, {f"manual_{reason}"})
        slog("manual_escalation", level=level.value, reason=reason)
        return True

    def get_escalation_status(self) -> Dict[str, Any]:
        """Get current escalation status for monitoring."""
        return {
            'current_level': self.current_level.value,
            'reasons': list(self.escalation_reasons),
            'risk_reduction_active': self._original_risk_percent is not None,
            'original_risk': self._original_risk_percent,
            'current_risk': self.trader.risk_manager.risk_percent,
            'escalation_history_count': len(self.escalation_history),
            'last_escalation': self.escalation_history[-1] if self.escalation_history else None
        }

    def check_and_escalate(self) -> RiskLevel:
        """Main method to check risk conditions and escalate if needed."""
        return self.evaluate_risk_level()


def init_risk_escalation(trader_instance):
    """Initialize risk escalation system for trader."""
    if not hasattr(trader_instance, 'risk_escalation'):
        trader_instance.risk_escalation = RiskEscalation(trader_instance)
        trader_instance.logger.info("Risk escalation system initialized")
    return trader_instance.risk_escalation


def check_risk_escalation(trader_instance) -> RiskLevel:
    """Convenience function to check and apply risk escalation."""
    if not hasattr(trader_instance, 'risk_escalation'):
        init_risk_escalation(trader_instance)

    return trader_instance.risk_escalation.check_and_escalate()
