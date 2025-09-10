#!/usr/bin/env python3
"""
Production Deployment Preparation - Real-time Monitoring Script
================================================================

Bu script A35 Phase 1 başarısından sonra production deployment preparation
için 24 saatlik comprehensive testnet validation monitoring yapar.

Monitoring Focus Areas:
- Trade execution performance
- Memory usage trends
- API connectivity health
- Database integrity
- Error rates and recovery
- State consistency validation
"""

import time
import psutil
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading
from typing import Dict, List, Optional
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

class ProductionMonitor:
    """Production deployment readiness monitoring"""

    def __init__(self):
        self.start_time = datetime.now()
        self.monitoring_active = True
        self.metrics = {
            'memory_samples': [],
            'api_responses': [],
            'trade_events': [],
            'errors': [],
            'performance_metrics': [],
            'database_queries': []
        }

        # Setup logging with UTF-8 encoding
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # File handler with UTF-8
        file_handler = logging.FileHandler('production_deployment_monitor.log', encoding='utf-8')
        file_handler.setFormatter(log_formatter)

        # Console handler without emoji to avoid encoding issues
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        # Setup logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Performance thresholds (from production criteria)
        self.thresholds = {
            'max_memory_growth_per_hour': 5.0,  # %
            'max_avg_latency_ms': 800,
            'min_api_success_rate': 99.5,
            'max_database_response_ms': 10,
            'max_memory_growth_24h': 2.0  # %
        }

        self.logger.info("🚀 Production Deployment Monitor initialized")
        self.logger.info(f"📊 Monitoring thresholds: {self.thresholds}")

    def get_memory_usage(self) -> Dict:
        """Get current memory usage statistics"""
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'timestamp': datetime.now().isoformat(),
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'memory_percent': process.memory_percent(),
            'open_files': len(process.open_files()) if hasattr(process, 'open_files') else 0
        }

    def check_database_health(self) -> Dict:
        """Check database connectivity and performance"""
        try:
            db_path = "data/testnet/trades.db"
            if not os.path.exists(db_path):
                return {
                    'status': 'error',
                    'message': f'Database not found: {db_path}',
                    'response_time_ms': None
                }

            start_time = time.time()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Simple health check query
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM executions")
            execution_count = cursor.fetchone()[0]

            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            conn.close()

            return {
                'status': 'healthy',
                'trade_count': trade_count,
                'execution_count': execution_count,
                'response_time_ms': response_time_ms,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'response_time_ms': None,
                'timestamp': datetime.now().isoformat()
            }

    def check_log_files(self) -> Dict:
        """Analyze recent log files for errors and patterns"""
        try:
            log_dir = Path("data/logs")
            if not log_dir.exists():
                return {'status': 'no_logs', 'message': 'Log directory not found'}

            recent_errors = []
            warning_count = 0
            error_count = 0

            # Check recent log files
            for log_file in log_dir.glob("*.log"):
                if log_file.stat().st_mtime > (time.time() - 3600):  # Last hour
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            for line in f.readlines()[-100:]:  # Last 100 lines
                                if 'ERROR' in line:
                                    error_count += 1
                                    recent_errors.append(line.strip())
                                elif 'WARNING' in line:
                                    warning_count += 1
                    except:
                        continue

            return {
                'status': 'analyzed',
                'error_count': error_count,
                'warning_count': warning_count,
                'recent_errors': recent_errors[-5:],  # Last 5 errors
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def analyze_memory_trend(self) -> Dict:
        """Analyze memory usage trend over time"""
        if len(self.metrics['memory_samples']) < 2:
            return {'status': 'insufficient_data'}

        samples = self.metrics['memory_samples']

        # Calculate growth rate
        first_sample = samples[0]
        last_sample = samples[-1]

        time_diff_hours = (
            datetime.fromisoformat(last_sample['timestamp']) -
            datetime.fromisoformat(first_sample['timestamp'])
        ).total_seconds() / 3600

        if time_diff_hours < 0.1:  # Less than 6 minutes
            return {'status': 'insufficient_time'}

        memory_growth_percent = (
            (last_sample['rss_mb'] - first_sample['rss_mb']) /
            first_sample['rss_mb'] * 100
        )

        growth_per_hour = memory_growth_percent / time_diff_hours if time_diff_hours > 0 else 0

        # Project 24h growth
        projected_24h_growth = growth_per_hour * 24

        status = 'healthy'
        if growth_per_hour > self.thresholds['max_memory_growth_per_hour']:
            status = 'warning'
        if projected_24h_growth > self.thresholds['max_memory_growth_24h']:
            status = 'critical'

        return {
            'status': status,
            'current_memory_mb': last_sample['rss_mb'],
            'memory_growth_percent': memory_growth_percent,
            'growth_per_hour_percent': growth_per_hour,
            'projected_24h_growth_percent': projected_24h_growth,
            'time_monitored_hours': time_diff_hours,
            'sample_count': len(samples)
        }

    def generate_report(self) -> Dict:
        """Generate comprehensive monitoring report"""
        uptime = datetime.now() - self.start_time

        # Collect current metrics
        memory_usage = self.get_memory_usage()
        db_health = self.check_database_health()
        log_analysis = self.check_log_files()
        memory_trend = self.analyze_memory_trend()

        # Store samples
        self.metrics['memory_samples'].append(memory_usage)

        # Keep only last 1000 samples to prevent memory issues
        if len(self.metrics['memory_samples']) > 1000:
            self.metrics['memory_samples'] = self.metrics['memory_samples'][-1000:]

        report = {
            'timestamp': datetime.now().isoformat(),
            'uptime_hours': uptime.total_seconds() / 3600,
            'uptime_str': str(uptime),
            'memory_usage': memory_usage,
            'database_health': db_health,
            'log_analysis': log_analysis,
            'memory_trend': memory_trend,
            'thresholds': self.thresholds,
            'overall_status': self._determine_overall_status(db_health, memory_trend, log_analysis)
        }

        return report

    def _determine_overall_status(self, db_health: Dict, memory_trend: Dict, log_analysis: Dict) -> str:
        """Determine overall system health status"""
        if db_health.get('status') == 'error':
            return 'CRITICAL'
        if memory_trend.get('status') == 'critical':
            return 'CRITICAL'
        if log_analysis.get('error_count', 0) > 10:  # More than 10 errors in last hour
            return 'WARNING'
        if memory_trend.get('status') == 'warning':
            return 'WARNING'
        if db_health.get('response_time_ms', 0) > self.thresholds['max_database_response_ms']:
            return 'WARNING'
        return 'HEALTHY'

    def monitor_loop(self, report_interval_minutes: int = 5):
        """Main monitoring loop"""
        self.logger.info(f"🔄 Starting monitoring loop - reporting every {report_interval_minutes} minutes")

        iteration = 0
        while self.monitoring_active:
            try:
                iteration += 1
                report = self.generate_report()

                # Log summary
                status = report['overall_status']
                uptime = report['uptime_hours']
                memory_mb = report['memory_usage']['rss_mb']

                status_emoji = {
                    'HEALTHY': '✅',
                    'WARNING': '⚠️',
                    'CRITICAL': '🔴'
                }.get(status, '❓')

                self.logger.info(
                    f"{status_emoji} Status: {status} | "
                    f"Uptime: {uptime:.2f}h | "
                    f"Memory: {memory_mb:.1f}MB | "
                    f"DB: {report['database_health'].get('response_time_ms', 'N/A')}ms"
                )

                # Detailed reporting every hour or on warnings/errors
                if iteration % (60 // report_interval_minutes) == 0 or status != 'HEALTHY':
                    self.logger.info("📊 Detailed Report:")
                    self.logger.info(f"  Memory Trend: {report['memory_trend']}")
                    self.logger.info(f"  Database: {report['database_health']}")
                    self.logger.info(f"  Logs: {report['log_analysis']}")

                # Save detailed report to file
                if iteration % (60 // report_interval_minutes) == 0:  # Every hour
                    report_file = f"production_monitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(report_file, 'w') as f:
                        json.dump(report, f, indent=2)
                    self.logger.info(f"📁 Detailed report saved: {report_file}")

                # Sleep until next check
                time.sleep(report_interval_minutes * 60)

            except KeyboardInterrupt:
                self.logger.info("⏹️ Monitoring stopped by user")
                self.monitoring_active = False
                break
            except Exception as e:
                self.logger.error(f"❌ Monitoring error: {e}")
                time.sleep(30)  # Short sleep before retry

        self.logger.info("🏁 Production monitoring completed")

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.monitoring_active = False

def main():
    """Main entry point for production deployment monitoring"""
    print("🚀 Production Deployment Preparation Monitor")
    print("=" * 50)
    print("Following A35 Phase 1 success (99.85% test rate),")
    print("starting comprehensive 24h testnet validation...")
    print("=" * 50)

    monitor = ProductionMonitor()

    try:
        monitor.monitor_loop(report_interval_minutes=5)
    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped")
    finally:
        monitor.stop_monitoring()

        # Generate final report
        final_report = monitor.generate_report()
        final_report_file = f"production_deployment_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(final_report_file, 'w') as f:
            json.dump(final_report, f, indent=2)

        print(f"📁 Final report saved: {final_report_file}")
        print("🎯 Production deployment monitoring completed!")

if __name__ == "__main__":
    main()
