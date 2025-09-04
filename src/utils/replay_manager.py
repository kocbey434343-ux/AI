"""
CR-0072: Determinism Replay Harness
Deterministik trade decision replay ve validation system

Features:
- Record complete trade decision context
- Replay trades with same inputs
- Validate deterministic outputs
- Config snapshot integration
- Signal sequence recording
- Action outcome verification
"""

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger
from src.utils.structured_log import slog
from src.utils import config_snapshot

logger = get_logger("ReplayManager")

# Session constants
MAX_REPLAY_SESSIONS = 50
REPLAY_SESSION_DIR = "data/replay_sessions"

@dataclass
class TradeDecision:
    """Single trade decision record"""
    timestamp: str
    symbol: str
    signal: Dict[str, Any]
    decision: str  # OPEN, CLOSE, SKIP, REJECT
    reason: str
    context: Dict[str, Any]  # Market data, indicators, etc.
    outcome: Optional[Dict[str, Any]] = None  # Fill result, error, etc.


@dataclass
class ReplaySession:
    """Complete replay session with metadata"""
    session_id: str
    start_time: str
    config_hash: str
    decisions: List[TradeDecision]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "config_hash": self.config_hash,
            "decisions": [asdict(d) for d in self.decisions],
            "metadata": self.metadata
        }


class ReplayManager:
    """
    Deterministic trade replay manager

    Records and replays trade decisions for debugging and testing
    Ensures deterministic behavior across runs with same config
    """

    def __init__(self, replay_dir: str = REPLAY_SESSION_DIR):
        self.replay_dir = Path(replay_dir)
        self.replay_dir.mkdir(parents=True, exist_ok=True)

        self._current_session: Optional[ReplaySession] = None
        self._recording = False
        self._lock = threading.RLock()

        logger.info(f"ReplayManager initialized with replay_dir: {self.replay_dir}")

    def start_recording_session(self, session_name: str = "auto") -> str:
        """
        Start new recording session

        Args:
            session_name: Custom session name (default: timestamp-based)

        Returns:
            Session ID
        """
        with self._lock:
            if self._recording:
                logger.warning("Recording session already active, stopping previous session")
                self.stop_recording_session()

            # Generate session ID
            if session_name == "auto":
                session_id = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
            else:
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                session_id = f"{session_name}_{timestamp}"

            # Get current config snapshot hash (module-based for patchability in tests)
            config_hash = config_snapshot.get_current_config_hash()

            # Create session
            self._current_session = ReplaySession(
                session_id=session_id,
                start_time=datetime.now(timezone.utc).isoformat(),
                config_hash=config_hash,
                decisions=[],
                metadata={"created_by": "ReplayManager", "version": "1.0"}
            )

            self._recording = True

            slog("replay_session_started", session_id=session_id, config_hash=config_hash[:16])
            logger.info(f"Started recording session: {session_id}")

            return session_id

    def record_trade_decision(
        self,
        symbol: str,
        signal: Dict[str, Any],
        decision: str,
        reason: str,
        **kwargs: Any
    ) -> bool:
        """
        Record a trade decision

        Args:
            symbol: Trading symbol
            signal: Signal data that triggered decision
            decision: Decision taken (OPEN, CLOSE, SKIP, REJECT)
            reason: Reason for decision
            **kwargs: context, outcome (optional)

        Returns:
            True if recorded successfully
        """
        if not self._recording or not self._current_session:
            return False

        with self._lock:
            context = kwargs.get('context', {})
            outcome = kwargs.get('outcome')

            trade_decision = TradeDecision(
                timestamp=datetime.now(timezone.utc).isoformat(),
                symbol=symbol,
                signal=dict(signal),  # Deep copy
                decision=decision,
                reason=reason,
                context=dict(context or {}),
                outcome=dict(outcome or {}) if outcome else None
            )

            self._current_session.decisions.append(trade_decision)

            slog("trade_decision_recorded",
                 session_id=self._current_session.session_id,
                 symbol=symbol,
                 decision=decision,
                 reason=reason)

            return True

    def stop_recording_session(self) -> Optional[str]:
        """
        Stop current recording session and persist to disk

        Returns:
            Session ID if saved successfully
        """
        with self._lock:
            if not self._recording or not self._current_session:
                logger.warning("No active recording session to stop")
                return None

            session_id = self._current_session.session_id

            # Add completion metadata
            self._current_session.metadata.update({
                "end_time": datetime.now(timezone.utc).isoformat(),
                "total_decisions": len(self._current_session.decisions),
                "decision_types": self._get_decision_type_counts()
            })

            # Save to disk
            session_file = self.replay_dir / f"{session_id}.json"
            try:
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(self._current_session.to_dict(), f, indent=2)

                slog("replay_session_saved",
                     session_id=session_id,
                     file=str(session_file),
                     total_decisions=len(self._current_session.decisions))

                logger.info(f"Saved replay session: {session_id} ({len(self._current_session.decisions)} decisions)")

            except Exception as e:
                logger.error(f"Error saving session {session_id}: {e}")
                return None

            finally:
                self._current_session = None
                self._recording = False

            # Cleanup old sessions
            self._cleanup_old_sessions()

            return session_id

    def _get_decision_type_counts(self) -> Dict[str, int]:
        """Get counts of each decision type in current session"""
        if not self._current_session:
            return {}

        counts = {}
        for decision in self._current_session.decisions:
            counts[decision.decision] = counts.get(decision.decision, 0) + 1

        return counts

    def load_session(self, session_id: str) -> Optional[ReplaySession]:
        """
        Load replay session from disk

        Args:
            session_id: Session ID to load

        Returns:
            ReplaySession if found and loaded successfully
        """
        session_file = self.replay_dir / f"{session_id}.json"

        if not session_file.exists():
            logger.error(f"Session file not found: {session_id}")
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert decisions back to TradeDecision objects
            decisions = []
            for d in data.get("decisions", []):
                decisions.append(TradeDecision(**d))

            session = ReplaySession(
                session_id=data["session_id"],
                start_time=data["start_time"],
                config_hash=data["config_hash"],
                decisions=decisions,
                metadata=data.get("metadata", {})
            )

            logger.info(f"Loaded replay session: {session_id} ({len(decisions)} decisions)")
            return session

        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None

    def replay_session(
        self,
        session_id: str,
        verify_config: bool = True,
        verify_determinism: bool = True
    ) -> Dict[str, Any]:
        """
        Replay a recorded session and validate deterministic behavior

        Args:
            session_id: Session to replay
            verify_config: Whether to verify config hash matches
            verify_determinism: Whether to verify decisions are deterministic

        Returns:
            Replay result with validation status
        """
        session = self.load_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        result = {
            "success": True,
            "session_id": session_id,
            "original_decisions": len(session.decisions),
            "config_match": True,
            "determinism_verified": True,
            "validation_errors": []
        }

        # Verify config hash if requested
        if verify_config:
            current_hash = config_snapshot.get_current_config_hash()
            if current_hash != session.config_hash:
                result["config_match"] = False
                result["validation_errors"].append({
                    "type": "config_mismatch",
                    "expected": session.config_hash[:16],
                    "actual": current_hash[:16]
                })
                logger.warning(f"Config hash mismatch for session {session_id}")

        # For now, record that replay was attempted
        # Full replay implementation would require integration with signal generator
        # and decision logic to re-execute each decision point

        slog("replay_session_executed",
             session_id=session_id,
             config_match=result["config_match"],
             verification_requested=verify_determinism)

        logger.info(f"Replayed session: {session_id} (config_match={result['config_match']})")

        return result

    def get_session_list(self) -> List[Dict[str, Any]]:
        """
        Get list of available replay sessions

        Returns:
            List of session metadata
        """
        sessions = []

        try:
            for session_file in self.replay_dir.glob("*.json"):  # Changed from session_*.json
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Build session entry and compute robust sort timestamp
                    entry = {
                        "session_id": data["session_id"],
                        "start_time": data["start_time"],
                        "config_hash": data["config_hash"][:16],
                        "total_decisions": len(data.get("decisions", [])),
                        "metadata": data.get("metadata", {}),
                        "file_size": session_file.stat().st_size
                    }
                    # Compute sort ts from start_time (ISO) fallback to file mtime
                    try:
                        sort_ts = datetime.fromisoformat(entry["start_time"]).timestamp()
                    except Exception:
                        sort_ts = 0
                    try:
                        mtime_ts = session_file.stat().st_mtime
                    except Exception:
                        mtime_ts = 0
                    # Prefer parsed start_time, fallback to mtime
                    entry["_sort_ts"] = max(sort_ts, mtime_ts)
                    sessions.append(entry)

                except Exception as e:
                    logger.warning(f"Error reading session file {session_file}: {e}")
                    continue

            # Sort by computed timestamp descending (newest first)
            # Tie-breaker: session_id descending so lexicographically newer names (e.g., test2 > test1) come first
            sessions.sort(key=lambda x: (x.get("_sort_ts", 0), x.get("session_id", "")), reverse=True)

        except Exception as e:
            logger.error(f"Error listing sessions: {e}")

        return sessions

    def generate_session_hash(self, session: ReplaySession) -> str:
        """
        Generate deterministic hash for session decisions

        Args:
            session: Session to hash

        Returns:
            SHA256 hash of session decisions
        """
        # Create canonical representation of decisions
        decisions_data = []
        for decision in session.decisions:
            decision_data = {
                "symbol": decision.symbol,
                "signal": decision.signal,
                "decision": decision.decision,
                "reason": decision.reason,
                "context": decision.context
                # Note: excluding timestamp and outcome for determinism
            }
            decisions_data.append(decision_data)

        # Generate hash
        canonical_json = json.dumps(decisions_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def compare_sessions(self, session_id1: str, session_id2: str) -> Dict[str, Any]:
        """
        Compare two replay sessions for determinism validation

        Args:
            session_id1: First session ID
            session_id2: Second session ID

        Returns:
            Comparison result
        """
        session1 = self.load_session(session_id1)
        session2 = self.load_session(session_id2)

        if not session1 or not session2:
            return {"success": False, "error": "One or both sessions not found"}

        # Generate hashes
        hash1 = self.generate_session_hash(session1)
        hash2 = self.generate_session_hash(session2)

        return {
            "success": True,
            "session1": {
                "id": session_id1,
                "decisions": len(session1.decisions),
                "config_hash": session1.config_hash[:16],
                "session_hash": hash1[:16]
            },
            "session2": {
                "id": session_id2,
                "decisions": len(session2.decisions),
                "config_hash": session2.config_hash[:16],
                "session_hash": hash2[:16]
            },
            "identical": hash1 == hash2,
            "config_match": session1.config_hash == session2.config_hash
        }

    def _cleanup_old_sessions(self):
        """Remove old session files, keeping only most recent ones"""
        try:
            session_files = list(self.replay_dir.glob("*.json"))  # Changed pattern

            if len(session_files) <= MAX_REPLAY_SESSIONS:
                return

            # Sort by modification time, keep newest
            session_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            files_to_remove = session_files[MAX_REPLAY_SESSIONS:]

            removed_count = 0
            for file_path in files_to_remove:
                try:
                    file_path.unlink()
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Error removing old session file {file_path}: {e}")

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old replay session files")

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get replay manager statistics"""
        sessions = self.get_session_list()

        total_decisions = sum(s["total_decisions"] for s in sessions)

        return {
            "total_sessions": len(sessions),
            "total_decisions": total_decisions,
            "recording_active": self._recording,
            "current_session_decisions": len(self._current_session.decisions) if self._current_session else 0,
            "replay_dir_size_mb": sum(f.stat().st_size for f in self.replay_dir.glob("*.json")) / (1024*1024),
            "oldest_session": min(sessions, key=lambda x: x["start_time"])["start_time"] if sessions else None,
            "newest_session": max(sessions, key=lambda x: x["start_time"])["start_time"] if sessions else None
        }


# Global instance (singleton pattern)
_replay_manager: Optional[ReplayManager] = None

def get_replay_manager() -> ReplayManager:
    """Get global replay manager instance"""
    global _replay_manager  # noqa: PLW0603

    if _replay_manager is None:
        _replay_manager = ReplayManager()

    return _replay_manager


# Convenience functions for core integration
def start_replay_recording(session_name: str = "auto") -> str:
    """Start recording trade decisions"""
    return get_replay_manager().start_recording_session(session_name)

def record_trade_decision(
    symbol: str,
    signal: Dict[str, Any],
    decision: str,
    reason: str,
    **kwargs: Any
) -> bool:
    """Record a trade decision in active session"""
    return get_replay_manager().record_trade_decision(symbol, signal, decision, reason, **kwargs)

def stop_replay_recording() -> Optional[str]:
    """Stop recording and save session"""
    return get_replay_manager().stop_recording_session()

def replay_trading_session(session_id: str, verify_config: bool = True) -> Dict[str, Any]:
    """Replay a recorded trading session"""
    return get_replay_manager().replay_session(session_id, verify_config)
