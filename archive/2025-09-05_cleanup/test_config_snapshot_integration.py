"""
CR-0071: Config snapshot integration test
"""

import os
from pathlib import Path

# Test config snapshot creation
os.environ['DISABLE_CONFIG_SNAPSHOT'] = 'false'

try:
    from src.trader.core import Trader

    print("Creating Trader with config snapshot enabled...")
    trader = Trader()
    print("✅ Trader created successfully")

    # Check if snapshot directory exists
    snapshot_dir = Path("data/config_snapshots")
    if snapshot_dir.exists():
        snapshots = list(snapshot_dir.glob("snapshot_*.json"))
        print(f"✅ Snapshots directory exists with {len(snapshots)} snapshots")

        if snapshots:
            # Show most recent snapshot
            recent_snapshot = sorted(snapshots, key=lambda x: x.stat().st_mtime)[-1]
            print(f"✅ Most recent snapshot: {recent_snapshot.name}")

            # Check snapshot size
            size_kb = recent_snapshot.stat().st_size / 1024
            print(f"✅ Snapshot size: {size_kb:.1f} KB")
        else:
            print("ℹ️ No snapshots found yet")
    else:
        print("❌ Snapshot directory not found")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
