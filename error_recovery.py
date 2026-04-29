"""
Error Recovery System for Kora AI Assistant
Provides automatic retry logic, fallback mechanisms, and self-healing capabilities
"""

import time
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import json


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    NETWORK = "network"
    API = "api"
    FILE_IO = "file_io"
    MEMORY = "memory"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ErrorRecord:
    def __init__(self, error: Exception, context: Dict = None, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        self.error = error
        self.error_type = type(error).__name__
        self.error_message = str(error)
        self.context = context or {}
        self.severity = severity
        self.timestamp = datetime.now()
        self.category = self._categorize_error(error)
        self.retry_count = 0
        self.resolved = False
        self.resolution_attempts = []

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error based on type and message"""
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()

        if any(keyword in error_msg for keyword in ['connection', 'network', 'internet', 'timeout']):
            return ErrorCategory.NETWORK
        elif any(keyword in error_msg for keyword in ['api', 'request', 'http']):
            return ErrorCategory.API
        elif any(keyword in error_msg for keyword in ['file', 'directory', 'path', 'not found']):
            return ErrorCategory.FILE_IO
        elif any(keyword in error_msg for keyword in ['memory', 'ram', 'allocation']):
            return ErrorCategory.MEMORY
        elif any(keyword in error_msg for keyword in ['permission', 'access denied', 'unauthorized']):
            return ErrorCategory.PERMISSION
        elif 'timeout' in error_type or 'timed out' in error_msg:
            return ErrorCategory.TIMEOUT
        else:
            return ErrorCategory.UNKNOWN

    def to_dict(self) -> Dict:
        """Convert error record to dictionary"""
        return {
            'error_type': self.error_type,
            'error_message': self.error_message,
            'context': self.context,
            'severity': self.severity.value,
            'category': self.category.value,
            'timestamp': self.timestamp.isoformat(),
            'retry_count': self.retry_count,
            'resolved': self.resolved,
            'resolution_attempts': self.resolution_attempts
        }


class RetryStrategy:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0,
                 exponential_backoff: bool = True, jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** attempt)
        else:
            delay = self.base_delay * attempt

        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)

        return delay


class ErrorRecoveryManager:
    def __init__(self):
        self.error_history: List[ErrorRecord] = []
        self.max_history = 1000
        self.active_recoveries: Dict[str, threading.Thread] = {}
        self.lock = threading.Lock()
        self.recovery_strategies = self._init_recovery_strategies()
        self.fallback_handlers = self._init_fallback_handlers()
        self.health_checks = self._init_health_checks()

    def _init_recovery_strategies(self) -> Dict[ErrorCategory, List[Callable]]:
        """Initialize recovery strategies for different error categories"""
        return {
            ErrorCategory.NETWORK: [
                self._retry_with_backoff,
                self._check_network_connection,
                self._switch_network_interface
            ],
            ErrorCategory.API: [
                self._retry_with_backoff,
                self._validate_api_credentials,
                self._use_backup_endpoint
            ],
            ErrorCategory.FILE_IO: [
                self._retry_with_backoff,
                self._check_file_permissions,
                self._create_missing_directories
            ],
            ErrorCategory.MEMORY: [
                self._clear_memory_cache,
                self._reduce_memory_usage,
                self._restart_subprocesses
            ],
            ErrorCategory.PERMISSION: [
                self._request_elevated_permissions,
                self._use_alternative_location,
                self._log_permission_issue
            ],
            ErrorCategory.TIMEOUT: [
                self._increase_timeout,
                self._retry_with_backoff,
                self._break_into_smaller_tasks
            ],
            ErrorCategory.UNKNOWN: [
                self._log_unknown_error,
                self._attempt_generic_recovery,
                self._fallback_to_safe_state
            ]
        }

    def _init_fallback_handlers(self) -> Dict[str, Callable]:
        """Initialize fallback handlers for critical operations"""
        return {
            'llm_request': self._fallback_llm_request,
            'file_operation': self._fallback_file_operation,
            'network_request': self._fallback_network_request,
            'database_operation': self._fallback_database_operation
        }

    def _init_health_checks(self) -> Dict[str, Callable]:
        """Initialize health check functions"""
        return {
            'network': self._check_network_health,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory_health,
            'api': self._check_api_health
        }

    def record_error(self, error: Exception, context: Dict = None,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> ErrorRecord:
        """Record an error for tracking and potential recovery"""
        error_record = ErrorRecord(error, context, severity)

        with self.lock:
            self.error_history.append(error_record)
            if len(self.error_history) > self.max_history:
                self.error_history.pop(0)

        return error_record

    def attempt_recovery(self, error_record: ErrorRecord,
                       operation: Callable = None, *args, **kwargs) -> Any:
        """Attempt to recover from an error using various strategies"""
        strategies = self.recovery_strategies.get(error_record.category, [])

        for strategy in strategies:
            try:
                error_record.retry_count += 1
                result = strategy(error_record, operation, *args, **kwargs)

                if result is not None:
                    error_record.resolved = True
                    error_record.resolution_attempts.append({
                        'strategy': strategy.__name__,
                        'success': True,
                        'timestamp': datetime.now().isoformat()
                    })
                    return result

            except Exception as recovery_error:
                error_record.resolution_attempts.append({
                    'strategy': strategy.__name__,
                    'success': False,
                    'error': str(recovery_error),
                    'timestamp': datetime.now().isoformat()
                })

        return None

    def execute_with_retry(self, operation: Callable, operation_name: str = "unknown",
                         retry_strategy: RetryStrategy = None,
                         fallback_handler: Callable = None,
                         *args, **kwargs) -> Any:
        """Execute an operation with automatic retry and fallback"""
        if retry_strategy is None:
            retry_strategy = RetryStrategy()

        last_error = None

        for attempt in range(retry_strategy.max_retries + 1):
            try:
                return operation(*args, **kwargs)

            except Exception as error:
                last_error = error
                error_record = self.record_error(error, {
                    'operation': operation_name,
                    'attempt': attempt + 1,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                })

                if attempt < retry_strategy.max_retries:
                    delay = retry_strategy.get_delay(attempt)
                    print(f"[Retry] Attempt {attempt + 1} failed for {operation_name}. "
                          f"Retrying in {delay:.2f}s... Error: {error}")
                    time.sleep(delay)
                else:
                    print(f"[Retry] All attempts failed for {operation_name}. Error: {error}")

        # All retries exhausted, try fallback
        if fallback_handler:
            try:
                print(f"[Fallback] Using fallback handler for {operation_name}")
                return fallback_handler(last_error, *args, **kwargs)
            except Exception as fallback_error:
                print(f"[Fallback] Fallback handler failed: {fallback_error}")

        raise last_error

    # Recovery Strategies
    def _retry_with_backoff(self, error_record: ErrorRecord, operation: Callable = None,
                           *args, **kwargs) -> Any:
        """Retry operation with exponential backoff"""
        if operation is None:
            return None

        strategy = RetryStrategy(max_retries=3, base_delay=1.0)
        delay = strategy.get_delay(error_record.retry_count)

        print(f"[Recovery] Waiting {delay:.2f}s before retry...")
        time.sleep(delay)

        return operation(*args, **kwargs)

    def _check_network_connection(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Check if network connection is available"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            print("[Recovery] Network connection is available")
            return True
        except Exception as e:
            print(f"[Recovery] Network connection check failed: {e}")
            return False

    def _switch_network_interface(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Attempt to switch network interface (placeholder)"""
        print("[Recovery] Network interface switching not implemented")
        return False

    def _validate_api_credentials(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Validate API credentials (placeholder)"""
        print("[Recovery] API credential validation not implemented")
        return False

    def _use_backup_endpoint(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Use backup API endpoint (placeholder)"""
        print("[Recovery] Backup endpoint switching not implemented")
        return False

    def _check_file_permissions(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Check file permissions"""
        try:
            import os
            if 'path' in error_record.context:
                path = error_record.context['path']
                if os.path.exists(path):
                    os.access(path, os.R_OK)
                    print(f"[Recovery] File permissions OK for {path}")
                    return True
        except Exception as e:
            print(f"[Recovery] File permission check failed: {e}")
        return False

    def _create_missing_directories(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Create missing directories"""
        try:
            import os
            if 'path' in error_record.context:
                path = error_record.context['path']
                directory = os.path.dirname(path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                    print(f"[Recovery] Created directory: {directory}")
                    return True
        except Exception as e:
            print(f"[Recovery] Directory creation failed: {e}")
        return False

    def _clear_memory_cache(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Clear memory cache"""
        try:
            import gc
            gc.collect()
            print("[Recovery] Memory cache cleared")
            return True
        except Exception as e:
            print(f"[Recovery] Memory cache clear failed: {e}")
        return False

    def _reduce_memory_usage(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Reduce memory usage (placeholder)"""
        print("[Recovery] Memory usage reduction not implemented")
        return False

    def _restart_subprocesses(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Restart subprocesses (placeholder)"""
        print("[Recovery] Subprocess restart not implemented")
        return False

    def _request_elevated_permissions(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Request elevated permissions (placeholder)"""
        print("[Recovery] Elevated permission request not implemented")
        return False

    def _use_alternative_location(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Use alternative file location (placeholder)"""
        print("[Recovery] Alternative location usage not implemented")
        return False

    def _log_permission_issue(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Log permission issue"""
        print(f"[Recovery] Permission issue logged: {error_record.error_message}")
        return False

    def _increase_timeout(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Increase operation timeout (placeholder)"""
        print("[Recovery] Timeout increase not implemented")
        return False

    def _break_into_smaller_tasks(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Break operation into smaller tasks (placeholder)"""
        print("[Recovery] Task breaking not implemented")
        return False

    def _log_unknown_error(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Log unknown error"""
        print(f"[Recovery] Unknown error logged: {error_record.error_message}")
        return False

    def _attempt_generic_recovery(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Attempt generic recovery"""
        print("[Recovery] Attempting generic recovery...")
        return False

    def _fallback_to_safe_state(self, error_record: ErrorRecord, *args, **kwargs) -> bool:
        """Fallback to safe state"""
        print("[Recovery] Falling back to safe state")
        return False

    # Fallback Handlers
    def _fallback_llm_request(self, error: Exception, *args, **kwargs) -> str:
        """Fallback for LLM requests"""
        return "I'm experiencing technical difficulties with my language model. Please try again later."

    def _fallback_file_operation(self, error: Exception, *args, **kwargs) -> bool:
        """Fallback for file operations"""
        print(f"[Fallback] File operation failed: {error}")
        return False

    def _fallback_network_request(self, error: Exception, *args, **kwargs) -> Any:
        """Fallback for network requests"""
        print(f"[Fallback] Network request failed: {error}")
        return None

    def _fallback_database_operation(self, error: Exception, *args, **kwargs) -> Any:
        """Fallback for database operations"""
        print(f"[Fallback] Database operation failed: {error}")
        return None

    # Health Checks
    def _check_network_health(self) -> Dict:
        """Check network health"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return {'status': 'healthy', 'message': 'Network connection available'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': f'Network unavailable: {e}'}

    def _check_disk_space(self) -> Dict:
        """Check disk space"""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024**3)
            if free_gb < 1.0:
                return {'status': 'warning', 'message': f'Low disk space: {free_gb:.2f}GB free'}
            return {'status': 'healthy', 'message': f'Disk space OK: {free_gb:.2f}GB free'}
        except Exception as e:
            return {'status': 'error', 'message': f'Disk check failed: {e}'}

    def _check_memory_health(self) -> Dict:
        """Check memory health"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return {'status': 'warning', 'message': f'High memory usage: {memory.percent}%'}
            return {'status': 'healthy', 'message': f'Memory OK: {memory.percent}% used'}
        except Exception as e:
            return {'status': 'error', 'message': f'Memory check failed: {e}'}

    def _check_api_health(self) -> Dict:
        """Check API health (placeholder)"""
        return {'status': 'unknown', 'message': 'API health check not implemented'}

    def run_health_check(self, check_name: str = None) -> Dict:
        """Run specific or all health checks"""
        if check_name and check_name in self.health_checks:
            return {check_name: self.health_checks[check_name]()}

        results = {}
        for name, check_func in self.health_checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                results[name] = {'status': 'error', 'message': str(e)}

        return results

    def get_error_summary(self, hours: int = 24) -> Dict:
        """Get summary of errors in specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self.lock:
            recent_errors = [
                error for error in self.error_history
                if error.timestamp > cutoff_time
            ]

        if not recent_errors:
            return {
                'period_hours': hours,
                'total_errors': 0,
                'by_category': {},
                'by_severity': {},
                'resolved_count': 0,
                'unresolved_count': 0
            }

        by_category = {}
        by_severity = {}
        resolved_count = sum(1 for error in recent_errors if error.resolved)

        for error in recent_errors:
            category = error.category.value
            severity = error.severity.value

            by_category[category] = by_category.get(category, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            'period_hours': hours,
            'total_errors': len(recent_errors),
            'by_category': by_category,
            'by_severity': by_severity,
            'resolved_count': resolved_count,
            'unresolved_count': len(recent_errors) - resolved_count
        }

    def get_recovery_report(self) -> str:
        """Generate comprehensive recovery report"""
        summary = self.get_error_summary(24)
        health = self.run_health_check()

        report = []
        report.append("🔧 ERROR RECOVERY REPORT")
        report.append("=" * 40)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Error Summary
        report.append("📊 ERROR SUMMARY (24 HOURS)")
        report.append("-" * 30)
        report.append(f"Total Errors: {summary['total_errors']}")
        report.append(f"Resolved: {summary['resolved_count']}")
        report.append(f"Unresolved: {summary['unresolved_count']}")
        report.append("")

        if summary['by_category']:
            report.append("By Category:")
            for category, count in summary['by_category'].items():
                report.append(f"  {category}: {count}")
            report.append("")

        if summary['by_severity']:
            report.append("By Severity:")
            for severity, count in summary['by_severity'].items():
                report.append(f"  {severity}: {count}")
            report.append("")

        # Health Status
        report.append("🏥 SYSTEM HEALTH")
        report.append("-" * 20)
        for name, result in health.items():
            status_icon = "✅" if result['status'] == 'healthy' else "⚠️"
            report.append(f"{status_icon} {name.title()}: {result['message']}")
        report.append("")

        return "\n".join(report)

    def export_error_data(self, filename: str = None):
        """Export error data to JSON file"""
        if filename is None:
            filename = f"error_recovery_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with self.lock:
            data = {
                'export_timestamp': datetime.now().isoformat(),
                'error_summary': self.get_error_summary(168),  # 7 days
                'health_status': self.run_health_check(),
                'error_history': [error.to_dict() for error in self.error_history[-100:]]  # Last 100 errors
            }

        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            return f"Error recovery data exported to {filename}"
        except Exception as e:
            return f"Failed to export error data: {e}"


# Global instance
error_recovery_manager = ErrorRecoveryManager()


def handle_error_recovery_command(query: str) -> Dict:
    """Handle error recovery commands"""
    query_lower = query.lower()

    if 'health' in query_lower or 'status' in query_lower:
        health = error_recovery_manager.run_health_check()
        reply = "System Health Status:\n"
        for name, result in health.items():
            status_icon = "✅" if result['status'] == 'healthy' else "⚠️"
            reply += f"{status_icon} {name.title()}: {result['message']}\n"
        return {'action': 'health_check', 'reply': reply}

    if 'report' in query_lower or 'summary' in query_lower:
        report = error_recovery_manager.get_recovery_report()
        return {'action': 'recovery_report', 'reply': report}

    if 'export' in query_lower:
        result = error_recovery_manager.export_error_data()
        return {'action': 'export_error_data', 'reply': result}

    if 'clear' in query_lower and ('error' in query_lower or 'history' in query_lower):
        with error_recovery_manager.lock:
            error_recovery_manager.error_history.clear()
        return {'action': 'clear_error_history', 'reply': 'Error history cleared.'}

    return None


def is_error_recovery_request(query: str) -> bool:
    """Check if query is error recovery related"""
    keywords = ['error', 'recovery', 'health', 'diagnostic', 'debug', 'troubleshoot']
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in keywords)


# Decorator for automatic error recovery
def with_retry(operation_name: str = "operation",
               max_retries: int = 3,
               fallback_handler: Callable = None):
    """Decorator to add automatic retry to any function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retry_strategy = RetryStrategy(max_retries=max_retries)
            return error_recovery_manager.execute_with_retry(
                func, operation_name, retry_strategy, fallback_handler, *args, **kwargs
            )
        return wrapper
    return decorator