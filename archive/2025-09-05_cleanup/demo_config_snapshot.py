"""
CR-0071: Core sistem entegrasyonu için config snapshot demo
"""

from src.utils.config_snapshot import (
    ConfigSnapshotManager,
    create_config_snapshot,
    get_current_config_hash,
    is_config_changed_since
)

def demo_config_snapshot():
    """Config snapshot sistem demonstrasyonu"""
    print("=== CR-0071 Config Snapshot Hash System Demo ===")

    # 1. Get current configuration hash
    print("\n1. Getting current configuration...")
    current_hash = get_current_config_hash()
    print(f"Current config hash: {current_hash[:16]}...")

    # 2. Create initial snapshot
    print("\n2. Creating initial snapshot...")
    snapshot_id, snapshot_hash = create_config_snapshot("demo_initial")
    print(f"Created snapshot: {snapshot_id}")
    print(f"Snapshot hash: {snapshot_hash[:16]}...")

    # 3. Check if config has changed
    print("\n3. Checking for configuration changes...")
    has_changed = is_config_changed_since(snapshot_hash)
    print(f"Config changed since snapshot: {has_changed}")

    # 4. Get manager and show statistics
    print("\n4. Getting snapshot statistics...")
    manager = ConfigSnapshotManager()
    stats = manager.get_statistics()
    print(f"Total snapshots: {stats['total_snapshots']}")
    print(f"Unique hashes: {stats['unique_hashes']}")
    print(f"Directory size: {stats['snapshot_dir_size_mb']:.2f} MB")

    # 5. Show recent history
    print("\n5. Recent snapshot history:")
    history = manager.get_snapshot_history(limit=5)
    for entry in history:
        print(f"  {entry['timestamp'][:19]} | {entry['reason']} | {entry['config_hash'][:16]}...")

    # 6. Show configuration structure
    print("\n6. Configuration structure:")
    config = manager.get_current_config()
    for source_name, source_data in config["sources"].items():
        print(f"  {source_name}: {len(source_data) if isinstance(source_data, dict) else type(source_data).__name__} items")

    print("\n=== Demo completed ===")

if __name__ == "__main__":
    demo_config_snapshot()
