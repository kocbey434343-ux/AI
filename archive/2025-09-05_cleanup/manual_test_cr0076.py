#!/usr/bin/env python3
"""Manual test of CR-0076 Risk Escalation System"""

import os
os.environ['TRADES_DB_PATH'] = ':memory:'

from src.trader.core import Trader
from src.utils.risk_escalation import RiskLevel

def test_basic_integration():
    """Test basic escalation integration."""
    print("=== CR-0076 Risk Escalation Integration Test ===")

    try:
        # Create trader instance
        trader = Trader()
        print(f"✓ Trader created successfully")

        # Check if risk_escalation is initialized
        has_escalation = hasattr(trader, 'risk_escalation')
        print(f"✓ Has risk_escalation attribute: {has_escalation}")

        if has_escalation:
            current_level = trader.risk_escalation.current_level
            print(f"✓ Current risk level: {current_level.value}")

            # Test force escalation
            result = trader.risk_escalation.force_escalation(RiskLevel.WARNING, "test")
            print(f"✓ Force escalation result: {result}")
            print(f"✓ New risk level: {trader.risk_escalation.current_level.value}")
            print(f"✓ Escalation reasons: {trader.risk_escalation.escalation_reasons}")

            # Test status reporting
            status = trader.risk_escalation.get_escalation_status()
            print(f"✓ Status report: {status}")

            # Test escalation check method
            trader._check_risk_escalation()
            print(f"✓ Risk escalation check completed")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_basic_integration()
