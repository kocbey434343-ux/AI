#!/usr/bin/env python3
"""
src/utils/scheduler.py

Bot Automation Scheduler Engine
Provides cron-like scheduling, market hours automation, and maintenance windows.

Features:
- Time-based bot scheduling (start/stop at specific times)
- Market hours automation (trading session aware)
- Maintenance windows (scheduled downtime)
- Auto risk reduction triggers
- Scheduled tasks (backup, cleanup, reporting)
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

# Setup logger
logger = logging.getLogger(__name__)

class TaskType(Enum):
    """Scheduled task types"""
    START_BOT = "start_bot"
    STOP_BOT = "stop_bot"
    RISK_REDUCTION = "risk_reduction"
    MAINTENANCE_START = "maintenance_start"
    MAINTENANCE_END = "maintenance_end"
    BACKUP = "backup"
    CLEANUP = "cleanup"
    REPORT = "report"
    CUSTOM = "custom"

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ScheduledTask:
    """Scheduled task definition"""
    id: str
    name: str
    task_type: TaskType
    cron_expression: str  # "HH:MM" or "* * * * *" format
    callback: Optional[Callable] = None
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    description: str = ""

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class MarketHours:
    """Market hours configuration"""

    # Cryptocurrency markets (24/7 but with optimal hours)
    CRYPTO_OPTIMAL_START = "09:00"  # UTC
    CRYPTO_OPTIMAL_END = "21:00"    # UTC

    # Maintenance windows (low activity periods)
    MAINTENANCE_WINDOW_START = "02:00"  # UTC
    MAINTENANCE_WINDOW_END = "04:00"    # UTC

    @staticmethod
    def is_optimal_trading_time(dt: Optional[datetime] = None) -> bool:
        """Check if current time is optimal for trading"""
        if dt is None:
            dt = datetime.now()

        current_time = dt.strftime("%H:%M")
        return MarketHours.CRYPTO_OPTIMAL_START <= current_time <= MarketHours.CRYPTO_OPTIMAL_END

    @staticmethod
    def is_maintenance_window(dt: Optional[datetime] = None) -> bool:
        """Check if current time is in maintenance window"""
        if dt is None:
            dt = datetime.now()

        current_time = dt.strftime("%H:%M")
        return MarketHours.MAINTENANCE_WINDOW_START <= current_time <= MarketHours.MAINTENANCE_WINDOW_END

class BotScheduler:
    """
    Advanced Bot Scheduler with automation capabilities
    """

    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.check_interval = 30  # seconds
        self.lock = threading.Lock()

        # Callbacks for bot operations
        self.start_bot_callback: Optional[Callable] = None
        self.stop_bot_callback: Optional[Callable] = None
        self.risk_reduction_callback: Optional[Callable] = None

        # Risk monitoring
        self.auto_risk_reduction_enabled = False
        self.risk_threshold_warning = 3.0  # %
        self.risk_threshold_critical = 5.0  # %

        logger.info("BotScheduler initialized")

    def set_callbacks(self,
                     start_bot: Optional[Callable] = None,
                     stop_bot: Optional[Callable] = None,
                     risk_reduction: Optional[Callable] = None):
        """Set callback functions for bot operations"""
        self.start_bot_callback = start_bot
        self.stop_bot_callback = stop_bot
        self.risk_reduction_callback = risk_reduction
        logger.info("Scheduler callbacks configured")

    def add_task(self, task: ScheduledTask) -> bool:
        """Add a new scheduled task"""
        try:
            with self.lock:
                # Calculate next run time
                task.next_run = self._calculate_next_run(task.cron_expression)
                self.tasks[task.id] = task

            logger.info(f"Added scheduled task: {task.name} ({task.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to add task {task.name}: {e}")
            return False

    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        try:
            with self.lock:
                if task_id in self.tasks:
                    removed_task = self.tasks.pop(task_id)
                    logger.info(f"Removed scheduled task: {removed_task.name}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove task {task_id}: {e}")
            return False

    def enable_task(self, task_id: str, enabled: bool = True) -> bool:
        """Enable or disable a scheduled task"""
        try:
            with self.lock:
                if task_id in self.tasks:
                    self.tasks[task_id].enabled = enabled
                    status = "enabled" if enabled else "disabled"
                    logger.info(f"Task {task_id} {status}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to modify task {task_id}: {e}")
            return False

    def get_tasks(self) -> List[ScheduledTask]:
        """Get all scheduled tasks"""
        with self.lock:
            return list(self.tasks.values())

    def get_next_tasks(self, count: int = 5) -> List[ScheduledTask]:
        """Get next N tasks to be executed"""
        with self.lock:
            enabled_tasks = [task for task in self.tasks.values() if task.enabled and task.next_run]
            # Filter out None values and sort
            enabled_tasks = [task for task in enabled_tasks if task.next_run is not None]
            # Type assertion since we filtered out None values
            enabled_tasks.sort(key=lambda t: t.next_run or datetime.min)
            return enabled_tasks[:count]

    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("BotScheduler started")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("BotScheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                self._check_and_execute_tasks()
                self._check_auto_risk_reduction()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                time.sleep(self.check_interval)

    def _check_and_execute_tasks(self):
        """Check for tasks that need to be executed"""
        now = datetime.now()

        with self.lock:
            for task in self.tasks.values():
                if (task.enabled and
                    task.next_run and
                    now >= task.next_run and
                    task.status != TaskStatus.RUNNING):

                    # Execute task in separate thread
                    threading.Thread(
                        target=self._execute_task,
                        args=(task,),
                        daemon=True
                    ).start()

    def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task"""
        try:
            task.status = TaskStatus.RUNNING
            task.last_run = datetime.now()

            logger.info(f"Executing task: {task.name} ({task.task_type.value})")

            # Execute based on task type
            success = False

            if task.task_type == TaskType.START_BOT:
                success = self._execute_start_bot()
            elif task.task_type == TaskType.STOP_BOT:
                success = self._execute_stop_bot()
            elif task.task_type == TaskType.RISK_REDUCTION:
                success = self._execute_risk_reduction()
            elif task.task_type == TaskType.MAINTENANCE_START:
                success = self._execute_maintenance_start()
            elif task.task_type == TaskType.MAINTENANCE_END:
                success = self._execute_maintenance_end()
            elif task.task_type == TaskType.BACKUP:
                success = self._execute_backup()
            elif task.task_type == TaskType.CLEANUP:
                success = self._execute_cleanup()
            elif task.task_type == TaskType.CUSTOM and task.callback:
                success = task.callback()

            # Update task status
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

            # Calculate next run time
            task.next_run = self._calculate_next_run(task.cron_expression)

            logger.info(f"Task {task.name} completed with status: {task.status.value}")

        except Exception as e:
            logger.error(f"Task execution failed for {task.name}: {e}")
            task.status = TaskStatus.FAILED

    def _execute_start_bot(self) -> bool:
        """Execute bot start task"""
        try:
            if self.start_bot_callback:
                return self.start_bot_callback()
            logger.warning("Start bot callback not set")
            return False
        except Exception as e:
            logger.error(f"Start bot execution failed: {e}")
            return False

    def _execute_stop_bot(self) -> bool:
        """Execute bot stop task"""
        try:
            if self.stop_bot_callback:
                return self.stop_bot_callback()
            logger.warning("Stop bot callback not set")
            return False
        except Exception as e:
            logger.error(f"Stop bot execution failed: {e}")
            return False

    def _execute_risk_reduction(self) -> bool:
        """Execute risk reduction task"""
        try:
            if self.risk_reduction_callback:
                return self.risk_reduction_callback()
            logger.warning("Risk reduction callback not set")
            return False
        except Exception as e:
            logger.error(f"Risk reduction execution failed: {e}")
            return False

    def _execute_maintenance_start(self) -> bool:
        """Execute maintenance start task"""
        try:
            # Stop trading but keep monitoring
            if self.stop_bot_callback:
                self.stop_bot_callback()
            logger.info("Maintenance window started - trading suspended")
            return True
        except Exception as e:
            logger.error(f"Maintenance start failed: {e}")
            return False

    def _execute_maintenance_end(self) -> bool:
        """Execute maintenance end task"""
        try:
            # Resume trading if market conditions are good
            if MarketHours.is_optimal_trading_time() and self.start_bot_callback:
                self.start_bot_callback()
            logger.info("Maintenance window ended - trading resumed")
            return True
        except Exception as e:
            logger.error(f"Maintenance end failed: {e}")
            return False

    def _execute_backup(self) -> bool:
        """Execute backup task"""
        try:
            # Placeholder for backup logic
            logger.info("Backup task executed")
            return True
        except Exception as e:
            logger.error(f"Backup execution failed: {e}")
            return False

    def _execute_cleanup(self) -> bool:
        """Execute cleanup task"""
        try:
            # Placeholder for cleanup logic
            logger.info("Cleanup task executed")
            return True
        except Exception as e:
            logger.error(f"Cleanup execution failed: {e}")
            return False

    def _check_auto_risk_reduction(self):
        """Check for automatic risk reduction triggers"""
        if not self.auto_risk_reduction_enabled:
            return

        try:
            # This would integrate with actual risk monitoring
            # For now, it's a placeholder
            current_risk = 0.0  # Get from risk monitoring system

            if current_risk > self.risk_threshold_critical:
                logger.warning(f"Critical risk level: {current_risk}% - triggering risk reduction")
                if self.risk_reduction_callback:
                    self.risk_reduction_callback()

        except Exception as e:
            logger.error(f"Auto risk reduction check failed: {e}")

    def _calculate_next_run(self, cron_expression: str) -> datetime:
        """Calculate next run time from cron expression"""
        try:
            # Simple implementation for HH:MM format
            if ":" in cron_expression:
                hour, minute = map(int, cron_expression.split(":"))
                now = datetime.now()
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # If time has passed today, schedule for tomorrow
                if next_run <= now:
                    next_run += timedelta(days=1)

                return next_run

            # For more complex cron expressions, would need a proper cron parser
            # For now, default to next hour
            return datetime.now() + timedelta(hours=1)

        except Exception as e:
            logger.error(f"Failed to calculate next run time for '{cron_expression}': {e}")
            return datetime.now() + timedelta(hours=1)

    def get_status_summary(self) -> Dict:
        """Get scheduler status summary"""
        with self.lock:
            total_tasks = len(self.tasks)
            enabled_tasks = len([t for t in self.tasks.values() if t.enabled])
            running_tasks = len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING])

            next_tasks = self.get_next_tasks(3)

            return {
                "running": self.running,
                "total_tasks": total_tasks,
                "enabled_tasks": enabled_tasks,
                "running_tasks": running_tasks,
                "next_task": next_tasks[0].name if next_tasks else None,
                "next_run_time": next_tasks[0].next_run.strftime("%H:%M") if next_tasks and next_tasks[0].next_run else None,
                "auto_risk_reduction": self.auto_risk_reduction_enabled,
                "market_optimal": MarketHours.is_optimal_trading_time(),
                "maintenance_window": MarketHours.is_maintenance_window()
            }

# Convenience functions for creating common tasks
def create_daily_start_task(time_str: str, task_id: Optional[str] = None) -> ScheduledTask:
    """Create a daily bot start task"""
    return ScheduledTask(
        id=task_id or f"daily_start_{time_str.replace(':', '')}",
        name=f"Daily Start at {time_str}",
        task_type=TaskType.START_BOT,
        cron_expression=time_str,
        description=f"Start bot daily at {time_str}"
    )

def create_daily_stop_task(time_str: str, task_id: Optional[str] = None) -> ScheduledTask:
    """Create a daily bot stop task"""
    return ScheduledTask(
        id=task_id or f"daily_stop_{time_str.replace(':', '')}",
        name=f"Daily Stop at {time_str}",
        task_type=TaskType.STOP_BOT,
        cron_expression=time_str,
        description=f"Stop bot daily at {time_str}"
    )

def create_maintenance_window(start_time: str, end_time: str) -> Tuple[ScheduledTask, ScheduledTask]:
    """Create maintenance window start and end tasks"""
    start_task = ScheduledTask(
        id=f"maintenance_start_{start_time.replace(':', '')}",
        name=f"Maintenance Start at {start_time}",
        task_type=TaskType.MAINTENANCE_START,
        cron_expression=start_time,
        description=f"Start maintenance window at {start_time}"
    )

    end_task = ScheduledTask(
        id=f"maintenance_end_{end_time.replace(':', '')}",
        name=f"Maintenance End at {end_time}",
        task_type=TaskType.MAINTENANCE_END,
        cron_expression=end_time,
        description=f"End maintenance window at {end_time}"
    )

    return start_task, end_task
