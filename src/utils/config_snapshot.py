"""
CR-0071: Config snapshot hash persist system
Deterministic configuration state management for replay and debugging
"""

import hashlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import Settings, RuntimeConfig
from src.utils.logger import get_logger

logger = get_logger("ConfigSnapshot")

# Constants
MAX_HISTORY_ENTRIES = 100


class ConfigSnapshotManager:
    """
    Configuration snapshot and hash management system

    Features:
    - Collect current configuration state from all sources
    - Generate deterministic hashes for config state
    - Persist snapshots with metadata
    - Compare configuration changes
    - History tracking
    - Rollback capability (optional)
    """

    def __init__(self, snapshot_dir: str = "data/config_snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.snapshot_dir / "config_history.json"
        # Uniqueness guard: per-instance monotonically increasing sequence and last ts(ms)
        self._last_ts_ms = None
        self._ts_counter = 0  # within the same millisecond
        self._seq = 0         # global per-instance sequence to guarantee uniqueness

        # Config source files
        self.config_files = {
            "runtime_thresholds": "config/runtime_thresholds.json",
            "indicators": "config/indicators.json",
            "runtime_costs": "config/runtime_costs.json",
            "param_overrides": "data/param_overrides.json"
        }

        logger.info(f"ConfigSnapshotManager initialized with snapshot_dir: {self.snapshot_dir}")

    def get_current_config(self) -> Dict[str, Any]:
        """
        Collect current configuration from all sources

        Returns:
            Complete configuration state dictionary
        """
        config = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": {}
        }

        # 1. Settings class - collect all attributes
        settings_config = {}
        for attr_name in dir(Settings):
            if not attr_name.startswith('_'):  # Skip private attributes
                attr_value = getattr(Settings, attr_name)
                # Only include basic data types and skip methods
                if not callable(attr_value) and not inspect.isclass(attr_value):
                    settings_config[attr_name] = self._serialize_value(attr_value)

        config["sources"]["settings"] = settings_config

        # 2. RuntimeConfig
        runtime_config = {}
        for attr_name in dir(RuntimeConfig):
            if not attr_name.startswith('_'):
                try:
                    attr_value = getattr(RuntimeConfig, attr_name)
                    # Only include basic data types and skip methods
                    if not callable(attr_value):
                        runtime_config[attr_name] = self._serialize_value(attr_value)
                except AttributeError:
                    # Skip attributes that don't exist
                    pass

        config["sources"]["runtime_config"] = runtime_config

        # 3. Config files
        for source_name, file_path in self.config_files.items():
            config["sources"][source_name] = self._load_config_file(file_path)

        return config

    def _serialize_value(self, value: Any) -> Any:
        """Convert value to JSON-serializable format"""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        # Convert other types to string
        return str(value)

    def _load_config_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found: {file_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading config file {file_path}: {e}")
            return {"error": str(e)}

    def generate_config_hash(self, config: Dict[str, Any]) -> str:
        """
        Generate deterministic hash for configuration state

        Args:
            config: Configuration dictionary

        Returns:
            SHA256 hash string
        """
        # Create a copy without timestamp for hashing
        hash_config = config.copy()
        hash_config.pop("timestamp", None)
        hash_config.pop("config_hash", None)

        # Convert to canonical JSON (sorted keys, no whitespace)
        canonical_json = json.dumps(hash_config, sort_keys=True, separators=(',', ':'))

        # Generate SHA256 hash
        hash_bytes = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

        logger.debug(f"Generated config hash: {hash_bytes[:16]}...")
        return hash_bytes

    def create_snapshot(self, reason: str = "manual") -> Tuple[str, str]:
        """
        Create a configuration snapshot

        Args:
            reason: Reason for creating snapshot

        Returns:
            Tuple of (snapshot_id, config_hash)
        """
        config = self.get_current_config()
        config_hash = self.generate_config_hash(config)

        # Add hash to config
        config["config_hash"] = config_hash
        config["reason"] = reason

        # Generate snapshot ID from timestamp (milliseconds) + per-instance sequence for strict uniqueness
        ts_ms = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        if self._last_ts_ms == ts_ms:
            self._ts_counter += 1
        else:
            self._last_ts_ms = ts_ms
            self._ts_counter = 0
        self._seq += 1

        # Include both global per-instance sequence and per-ms counter to avoid collisions
        base_snapshot_id = f"snapshot_{ts_ms}_{self._seq:03d}{self._ts_counter:02d}"
        snapshot_id = base_snapshot_id
        snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"

        # Extra safety: if a file somehow still exists, bump a local suffix until unique
        local_suffix = 0
        while snapshot_file.exists():
            local_suffix += 1
            snapshot_id = f"{base_snapshot_id}_{local_suffix}"
            snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"

        # Persist snapshot
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        # Update history
        self._update_history(snapshot_id, config_hash, reason)

        logger.info(f"Config snapshot created: {snapshot_id} (hash: {config_hash[:16]}...)")
        return snapshot_id, config_hash

    def _update_history(self, snapshot_id: str, config_hash: str, reason: str):
        """Update snapshot history file"""
        history = self._load_history()

        history_entry = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_hash": config_hash,
            "reason": reason
        }

        history.append(history_entry)

        # Keep only last entries
        if len(history) > MAX_HISTORY_ENTRIES:
            history = history[-MAX_HISTORY_ENTRIES:]

        # Save updated history
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load snapshot history"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading history: {e}")

        return []

    def load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific snapshot"""
        snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"

        try:
            if snapshot_file.exists():
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.error(f"Snapshot not found: {snapshot_id}")
                return None
        except Exception as e:
            logger.error(f"Error loading snapshot {snapshot_id}: {e}")
            return None

    def compare_snapshots(self, snapshot_id1: str, snapshot_id2: str) -> Dict[str, Any]:
        """
        Compare two snapshots and return differences

        Args:
            snapshot_id1: First snapshot ID
            snapshot_id2: Second snapshot ID

        Returns:
            Comparison result with differences
        """
        snapshot1 = self.load_snapshot(snapshot_id1)
        snapshot2 = self.load_snapshot(snapshot_id2)

        if not snapshot1 or not snapshot2:
            return {"error": "One or both snapshots not found"}

        return {
            "snapshot1": {
                "id": snapshot_id1,
                "timestamp": snapshot1.get("timestamp"),
                "hash": snapshot1.get("config_hash")
            },
            "snapshot2": {
                "id": snapshot_id2,
                "timestamp": snapshot2.get("timestamp"),
                "hash": snapshot2.get("config_hash")
            },
            "identical": snapshot1.get("config_hash") == snapshot2.get("config_hash"),
            "differences": self._find_differences(snapshot1["sources"], snapshot2["sources"])
        }

    def _find_differences(self, config1: Dict[str, Any], config2: Dict[str, Any], path: str = "") -> List[Dict[str, Any]]:
        """Recursively find differences between two config dictionaries"""
        differences = []

        # Check all keys in both configs
        all_keys = set(config1.keys()) | set(config2.keys())

        for key in sorted(all_keys):
            current_path = f"{path}.{key}" if path else key

            if key not in config1:
                differences.append({
                    "path": current_path,
                    "type": "added",
                    "value2": config2[key]
                })
            elif key not in config2:
                differences.append({
                    "path": current_path,
                    "type": "removed",
                    "value1": config1[key]
                })
            elif config1[key] != config2[key]:
                if isinstance(config1[key], dict) and isinstance(config2[key], dict):
                    # Recursively compare nested dictionaries
                    differences.extend(self._find_differences(config1[key], config2[key], current_path))
                else:
                    differences.append({
                        "path": current_path,
                        "type": "changed",
                        "value1": config1[key],
                        "value2": config2[key]
                    })

        return differences

    def get_snapshot_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get snapshot history (most recent first)"""
        history = self._load_history()
        return sorted(history, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_current_config_hash(self) -> str:
        """Get hash of current configuration state"""
        config = self.get_current_config()
        return self.generate_config_hash(config)

    def is_config_changed(self, reference_hash: str) -> bool:
        """Check if current config differs from reference hash"""
        current_hash = self.get_current_config_hash()
        return current_hash != reference_hash

    def cleanup_old_snapshots(self, keep_count: int = 50):
        """Clean up old snapshot files, keeping only the most recent ones"""
        history = self._load_history()

        if len(history) <= keep_count:
            return

        # Sort by timestamp and keep only the most recent
        sorted_history = sorted(history, key=lambda x: x["timestamp"], reverse=True)
        snapshots_to_keep = {entry["snapshot_id"] for entry in sorted_history[:keep_count]}

        # Remove old snapshot files
        removed_count = 0
        for snapshot_file in self.snapshot_dir.glob("snapshot_*.json"):
            snapshot_id = snapshot_file.stem
            if snapshot_id not in snapshots_to_keep:
                try:
                    snapshot_file.unlink()
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing snapshot file {snapshot_file}: {e}")

        # Update history to keep only recent entries
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(sorted_history[:keep_count], f, indent=2)

        logger.info(f"Cleaned up {removed_count} old snapshot files, kept {keep_count} recent ones")

    def get_statistics(self) -> Dict[str, Any]:
        """Get snapshot statistics"""
        history = self._load_history()
        snapshot_files = list(self.snapshot_dir.glob("snapshot_*.json"))

        return {
            "total_snapshots": len(history),
            "total_files": len(snapshot_files),
            "history_file_exists": self.history_file.exists(),
            "snapshot_dir_size_mb": sum(f.stat().st_size for f in snapshot_files) / (1024*1024),
            "oldest_snapshot": min(history, key=lambda x: x["timestamp"])["timestamp"] if history else None,
            "newest_snapshot": max(history, key=lambda x: x["timestamp"])["timestamp"] if history else None,
            "unique_hashes": len({entry["config_hash"] for entry in history})
        }


# Module-level instance
_config_snapshot_manager: Optional[ConfigSnapshotManager] = None

def get_config_snapshot_manager() -> ConfigSnapshotManager:
    """Get global config snapshot manager instance (singleton)"""
    global _config_snapshot_manager  # noqa: PLW0603

    if _config_snapshot_manager is None:
        _config_snapshot_manager = ConfigSnapshotManager()

    return _config_snapshot_manager

# Convenience functions
def create_config_snapshot(reason: str = "api") -> Tuple[str, str]:
    """Create configuration snapshot"""
    return get_config_snapshot_manager().create_snapshot(reason)

def get_current_config_hash() -> str:
    """Get current configuration hash"""
    return get_config_snapshot_manager().get_current_config_hash()

def is_config_changed_since(reference_hash: str) -> bool:
    """Check if configuration has changed since reference hash"""
    return get_config_snapshot_manager().is_config_changed(reference_hash)
