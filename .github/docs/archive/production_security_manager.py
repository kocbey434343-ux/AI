#!/usr/bin/env python3
"""
Production Security Configuration Manager
Phase 3: Production Environment Preparation
"""

import os
import json
import hashlib
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import configparser
from cryptography.fernet import Fernet
import keyring

class ProductionSecurityManager:
    """Manages production security configuration and secrets"""

    def __init__(self):
        self.setup_logging()
        self.config_dir = Path("config/production")
        self.secrets_dir = Path("secrets")
        self.ensure_directories()

        # Generate or load encryption key
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)

        self.logger.info("Production Security Manager initialized")

    def setup_logging(self):
        """Setup security logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [SECURITY] [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('production_security.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def ensure_directories(self):
        """Create necessary directories"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (Unix-like systems)
        if os.name != 'nt':  # Not Windows
            os.chmod(self.secrets_dir, 0o700)

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key"""
        key_file = self.secrets_dir / "master.key"

        if key_file.exists():
            with open(key_file, 'rb') as f:
                key = f.read()
            self.logger.info("Loaded existing encryption key")
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)

            # Set restrictive permissions
            if os.name != 'nt':
                os.chmod(key_file, 0o600)

            self.logger.info("Generated new encryption key")

        return key

    def encrypt_secret(self, value: str) -> str:
        """Encrypt a secret value"""
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_secret(self, encrypted_value: str) -> str:
        """Decrypt a secret value"""
        encrypted_bytes = base64.b64decode(encrypted_value.encode())
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()

    def store_api_credentials(self, api_key: str, api_secret: str, exchange: str = "binance"):
        """Securely store API credentials"""
        credentials = {
            "api_key": self.encrypt_secret(api_key),
            "api_secret": self.encrypt_secret(api_secret),
            "exchange": exchange,
            "created_at": datetime.now().isoformat(),
            "key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:16]
        }

        cred_file = self.secrets_dir / f"{exchange}_credentials.json"
        with open(cred_file, 'w') as f:
            json.dump(credentials, f, indent=2)

        # Set restrictive permissions
        if os.name != 'nt':
            os.chmod(cred_file, 0o600)

        self.logger.info(f"Stored encrypted {exchange} credentials (key hash: {credentials['key_hash']})")

    def load_api_credentials(self, exchange: str = "binance") -> Dict[str, str]:
        """Load and decrypt API credentials"""
        cred_file = self.secrets_dir / f"{exchange}_credentials.json"

        if not cred_file.exists():
            raise FileNotFoundError(f"Credentials not found for {exchange}")

        with open(cred_file, 'r') as f:
            credentials = json.load(f)

        return {
            "api_key": self.decrypt_secret(credentials["api_key"]),
            "api_secret": self.decrypt_secret(credentials["api_secret"]),
            "exchange": credentials["exchange"],
            "key_hash": credentials["key_hash"]
        }

    def generate_production_config(self) -> Dict[str, Any]:
        """Generate production configuration template"""
        config = {
            "environment": "production",
            "created_at": datetime.now().isoformat(),
            "version": "1.0.0",

            # API Configuration
            "api": {
                "use_testnet": False,
                "allow_production": True,
                "rate_limit_buffer_percent": 20,
                "connection_timeout_seconds": 30,
                "read_timeout_seconds": 60,
                "max_retries": 3,
                "retry_delay_seconds": 1
            },

            # Risk Management
            "risk": {
                "default_risk_percent": 1.0,
                "max_daily_loss_percent": 2.0,
                "max_consecutive_losses": 3,
                "position_size_limit_usdt": 1000,
                "max_open_positions": 3,
                "emergency_stop_enabled": True
            },

            # Monitoring
            "monitoring": {
                "prometheus_enabled": True,
                "metrics_port": 8090,
                "health_check_interval_seconds": 60,
                "log_level": "INFO",
                "structured_logging": True,
                "alert_thresholds": {
                    "memory_usage_mb": 200,
                    "cpu_usage_percent": 50,
                    "api_latency_ms": 1000,
                    "error_rate_percent": 1
                }
            },

            # Database
            "database": {
                "path": "data/production/trades.db",
                "backup_interval_hours": 1,
                "backup_retention_days": 30,
                "connection_pool_size": 5,
                "query_timeout_seconds": 10
            },

            # Security
            "security": {
                "secrets_encryption": True,
                "api_key_rotation_days": 90,
                "audit_logging": True,
                "ip_whitelist_enabled": False,
                "ssl_verify": True
            }
        }

        return config

    def save_production_config(self, config: Dict[str, Any]):
        """Save production configuration"""
        config_file = self.config_dir / "production.json"

        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        self.logger.info(f"Saved production configuration to {config_file}")

    def validate_production_setup(self) -> Dict[str, bool]:
        """Validate production setup requirements"""
        checks = {}

        # Check encryption key
        checks["encryption_key"] = (self.secrets_dir / "master.key").exists()

        # Check API credentials
        checks["api_credentials"] = (self.secrets_dir / "binance_credentials.json").exists()

        # Check production config
        checks["production_config"] = (self.config_dir / "production.json").exists()

        # Check directory permissions (Unix)
        if os.name != 'nt':
            stat_info = os.stat(self.secrets_dir)
            checks["secure_permissions"] = (stat_info.st_mode & 0o077) == 0
        else:
            checks["secure_permissions"] = True  # Windows handled differently

        # Check environment variables
        required_env_vars = ["USE_TESTNET", "BINANCE_API_KEY", "BINANCE_SECRET_KEY"]
        checks["environment_vars"] = all(var in os.environ for var in required_env_vars)

        return checks

    def generate_security_report(self) -> str:
        """Generate security configuration report"""
        validation = self.validate_production_setup()

        report = f"""
PRODUCTION SECURITY CONFIGURATION REPORT
=========================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Security Components Status:
"""

        for check, status in validation.items():
            status_icon = "✅" if status else "❌"
            report += f"  {status_icon} {check.replace('_', ' ').title()}: {'PASS' if status else 'FAIL'}\n"

        overall_status = "READY" if all(validation.values()) else "NOT READY"
        report += f"\nOverall Status: {overall_status}\n"

        if not all(validation.values()):
            report += "\nRequired Actions:\n"
            for check, status in validation.items():
                if not status:
                    report += f"  - Fix {check.replace('_', ' ')}\n"

        return report

    def setup_production_environment(self, api_key: str = None, api_secret: str = None):
        """Complete production environment setup"""
        self.logger.info("Starting production environment setup...")

        # Generate production configuration
        config = self.generate_production_config()
        self.save_production_config(config)

        # Store API credentials if provided
        if api_key and api_secret:
            self.store_api_credentials(api_key, api_secret)

        # Create environment file template
        env_template = """# Production Environment Configuration
# Generated: {timestamp}

# Trading Configuration
USE_TESTNET=false
ALLOW_PROD=true

# API Credentials (use encrypted storage in production)
BINANCE_API_KEY=your_production_api_key
BINANCE_SECRET_KEY=your_production_secret_key

# Risk Management
DEFAULT_RISK_PERCENT=1.0
MAX_DAILY_LOSS_PCT=2.0
MAX_OPEN_POSITIONS=3

# Monitoring
PROMETHEUS_ENABLED=true
METRICS_PORT=8090
LOG_LEVEL=INFO

# Security
SECRETS_ENCRYPTION=true
AUDIT_LOGGING=true
""".format(timestamp=datetime.now().isoformat())

        env_file = self.config_dir / "production.env"
        with open(env_file, 'w') as f:
            f.write(env_template)

        # Set restrictive permissions
        if os.name != 'nt':
            os.chmod(env_file, 0o600)

        self.logger.info("Production environment setup completed")

        # Generate and return security report
        return self.generate_security_report()

def main():
    """Main function for production security setup"""
    print("Production Security Configuration Manager")
    print("=" * 50)
    print("Phase 3: Production Environment Preparation")
    print("=" * 50)

    try:
        security_manager = ProductionSecurityManager()

        # Setup production environment
        report = security_manager.setup_production_environment()

        print("\nProduction Security Setup Results:")
        print(report)

        print("\nNext Steps:")
        print("1. Review and update production.json configuration")
        print("2. Add your production API credentials")
        print("3. Set up monitoring and alerting")
        print("4. Validate security configuration")
        print("5. Proceed to performance optimization")

    except Exception as e:
        print(f"Setup failed: {e}")
        logging.error(f"Production security setup failed: {e}")

if __name__ == "__main__":
    main()
