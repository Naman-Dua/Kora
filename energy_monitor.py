"""
Energy Monitoring Module for Kora AI Assistant
Tracks and optimizes energy usage including CPU, GPU, and system power consumption
"""

import psutil
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading


class EnergyMonitor:
    def __init__(self):
        self.monitoring = False
        self.history = []
        self.max_history = 1000  # Keep last 1000 data points
        self.baseline_usage = None
        self.optimization_suggestions = []
        self.monitor_thread = None
        self.lock = threading.Lock()

    def start_monitoring(self, interval: int = 60):
        """Start monitoring energy usage at specified interval (seconds)"""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop monitoring energy usage"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def _monitor_loop(self, interval: int):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                data = self._collect_energy_data()
                with self.lock:
                    self.history.append(data)
                    if len(self.history) > self.max_history:
                        self.history.pop(0)

                    # Update baseline if not set
                    if self.baseline_usage is None and len(self.history) >= 10:
                        self._calculate_baseline()

                    # Check for optimization opportunities
                    if self.baseline_usage:
                        self._check_optimization_opportunities(data)

            except Exception as e:
                print(f"[Energy Monitor Error] {e}")

            time.sleep(interval)

    def _collect_energy_data(self) -> Dict:
        """Collect current energy usage data"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()

            # Memory metrics
            memory = psutil.virtual_memory()

            # Disk metrics
            disk = psutil.disk_usage('/')

            # Network metrics
            network = psutil.net_io_counters()

            # Process information
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent'] > 1.0:  # Only significant processes
                        processes.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'cpu_percent': proc_info['cpu_percent'],
                            'memory_percent': proc_info['memory_percent']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)

            return {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'frequency_mhz': cpu_freq.current if cpu_freq else 0
                },
                'memory': {
                    'percent': memory.percent,
                    'total_gb': memory.total / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'used_gb': memory.used / (1024**3)
                },
                'disk': {
                    'percent': disk.percent,
                    'total_gb': disk.total / (1024**3),
                    'used_gb': disk.used / (1024**3),
                    'free_gb': disk.free / (1024**3)
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'top_processes': processes[:10],  # Top 10 processes
                'power_estimate': self._estimate_power_usage(cpu_percent, memory.percent)
            }
        except Exception as e:
            print(f"[Energy Data Collection Error] {e}")
            return {}

    def _estimate_power_usage(self, cpu_percent: float, memory_percent: float) -> Dict:
        """Estimate power usage based on system metrics"""
        # These are rough estimates - actual power monitoring would require hardware sensors
        base_power = 15  # Base system power in watts
        cpu_power = (cpu_percent / 100) * 65  # Up to 65W for CPU
        memory_power = (memory_percent / 100) * 10  # Up to 10W for memory

        total_power = base_power + cpu_power + memory_power

        return {
            'total_watts': round(total_power, 2),
            'cpu_watts': round(cpu_power, 2),
            'memory_watts': round(memory_power, 2),
            'base_watts': base_power
        }

    def _calculate_baseline(self):
        """Calculate baseline usage from historical data"""
        if len(self.history) < 10:
            return

        recent_data = self.history[-10:]

        cpu_avg = sum(d['cpu']['percent'] for d in recent_data) / len(recent_data)
        memory_avg = sum(d['memory']['percent'] for d in recent_data) / len(recent_data)
        power_avg = sum(d['power_estimate']['total_watts'] for d in recent_data) / len(recent_data)

        self.baseline_usage = {
            'cpu_percent': cpu_avg,
            'memory_percent': memory_avg,
            'power_watts': power_avg,
            'timestamp': datetime.now().isoformat()
        }

    def _check_optimization_opportunities(self, current_data: Dict):
        """Check for energy optimization opportunities"""
        if not self.baseline_usage:
            return

        suggestions = []

        # Check CPU usage
        cpu_increase = current_data['cpu']['percent'] - self.baseline_usage['cpu_percent']
        if cpu_increase > 20:
            suggestions.append({
                'type': 'cpu',
                'severity': 'high' if cpu_increase > 40 else 'medium',
                'message': f"CPU usage is {cpu_increase:.1f}% above baseline",
                'suggestion': "Consider closing unnecessary applications or reducing background processes"
            })

        # Check memory usage
        memory_increase = current_data['memory']['percent'] - self.baseline_usage['memory_percent']
        if memory_increase > 15:
            suggestions.append({
                'type': 'memory',
                'severity': 'high' if memory_increase > 30 else 'medium',
                'message': f"Memory usage is {memory_increase:.1f}% above baseline",
                'suggestion': "Close memory-intensive applications or clear browser cache"
            })

        # Check for power-hungry processes
        for proc in current_data['top_processes'][:3]:
            if proc['cpu_percent'] > 10:
                suggestions.append({
                    'type': 'process',
                    'severity': 'medium',
                    'message': f"High CPU usage from {proc['name']} ({proc['cpu_percent']:.1f}%)",
                    'suggestion': f"Consider closing {proc['name']} if not needed"
                })

        # Check power estimate
        power_increase = current_data['power_estimate']['total_watts'] - self.baseline_usage['power_watts']
        if power_increase > 10:
            suggestions.append({
                'type': 'power',
                'severity': 'high' if power_increase > 20 else 'medium',
                'message': f"Power usage is {power_increase:.1f}W above baseline",
                'suggestion': "System is consuming more power than usual - check running applications"
            })

        self.optimization_suggestions = suggestions

    def get_current_stats(self) -> Dict:
        """Get current energy statistics"""
        with self.lock:
            if not self.history:
                return {}
            return self.history[-1].copy()

    def get_historical_stats(self, hours: int = 24) -> Dict:
        """Get historical statistics for specified time period"""
        with self.lock:
            if not self.history:
                return {}

            cutoff_time = datetime.now() - timedelta(hours=hours)
            relevant_data = [
                d for d in self.history
                if datetime.fromisoformat(d['timestamp']) > cutoff_time
            ]

            if not relevant_data:
                return {}

            # Calculate statistics
            cpu_values = [d['cpu']['percent'] for d in relevant_data]
            memory_values = [d['memory']['percent'] for d in relevant_data]
            power_values = [d['power_estimate']['total_watts'] for d in relevant_data]

            return {
                'period_hours': hours,
                'data_points': len(relevant_data),
                'cpu': {
                    'avg': sum(cpu_values) / len(cpu_values),
                    'max': max(cpu_values),
                    'min': min(cpu_values)
                },
                'memory': {
                    'avg': sum(memory_values) / len(memory_values),
                    'max': max(memory_values),
                    'min': min(memory_values)
                },
                'power': {
                    'avg_watts': sum(power_values) / len(power_values),
                    'max_watts': max(power_values),
                    'min_watts': min(power_values),
                    'total_kwh': (sum(power_values) / len(power_values)) * hours / 1000  # Rough estimate
                }
            }

    def get_optimization_suggestions(self) -> List[Dict]:
        """Get current optimization suggestions"""
        with self.lock:
            return self.optimization_suggestions.copy()

    def get_energy_report(self) -> str:
        """Generate a comprehensive energy report"""
        current = self.get_current_stats()
        historical = self.get_historical_stats(hours=24)
        suggestions = self.get_optimization_suggestions()

        if not current:
            return "No energy data available yet. Monitoring will begin shortly."

        report = []
        report.append("📊 ENERGY MONITORING REPORT")
        report.append("=" * 40)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Current Status
        report.append("⚡ CURRENT STATUS")
        report.append("-" * 20)
        report.append(f"CPU Usage: {current['cpu']['percent']:.1f}%")
        report.append(f"Memory Usage: {current['memory']['percent']:.1f}%")
        report.append(f"Disk Usage: {current['disk']['percent']:.1f}%")
        report.append(f"Estimated Power: {current['power_estimate']['total_watts']:.1f}W")
        report.append("")

        # Top Processes
        if current['top_processes']:
            report.append("🔥 TOP POWER-CONSUMING PROCESSES")
            report.append("-" * 35)
            for i, proc in enumerate(current['top_processes'][:5], 1):
                report.append(f"{i}. {proc['name']}: CPU {proc['cpu_percent']:.1f}%, Memory {proc['memory_percent']:.1f}%")
            report.append("")

        # Historical Statistics
        if historical:
            report.append("📈 24-HOUR STATISTICS")
            report.append("-" * 25)
            report.append(f"Average CPU: {historical['cpu']['avg']:.1f}% (max: {historical['cpu']['max']:.1f}%)")
            report.append(f"Average Memory: {historical['memory']['avg']:.1f}% (max: {historical['memory']['max']:.1f}%)")
            report.append(f"Average Power: {historical['power']['avg_watts']:.1f}W (max: {historical['power']['max_watts']:.1f}W)")
            report.append(f"Estimated Energy Used: {historical['power']['total_kwh']:.3f} kWh")
            report.append("")

        # Optimization Suggestions
        if suggestions:
            report.append("💡 OPTIMIZATION SUGGESTIONS")
            report.append("-" * 30)
            for suggestion in suggestions:
                severity_icon = "🔴" if suggestion['severity'] == 'high' else "🟡"
                report.append(f"{severity_icon} {suggestion['message']}")
                report.append(f"   → {suggestion['suggestion']}")
            report.append("")
        else:
            report.append("✅ No optimization issues detected")
            report.append("")

        return "\n".join(report)

    def export_data(self, filename: str = None):
        """Export energy monitoring data to JSON file"""
        if filename is None:
            filename = f"energy_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with self.lock:
            data = {
                'export_timestamp': datetime.now().isoformat(),
                'baseline_usage': self.baseline_usage,
                'current_suggestions': self.optimization_suggestions,
                'history': self.history
            }

        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            return f"Energy data exported to {filename}"
        except Exception as e:
            return f"Failed to export data: {e}"


# Global instance
energy_monitor = EnergyMonitor()


def handle_energy_command(query: str) -> Dict:
    """Handle energy-related commands"""
    query_lower = query.lower()

    if 'start' in query_lower and 'monitor' in query_lower:
        energy_monitor.start_monitoring()
        return {
            'action': 'start_monitoring',
            'reply': "Energy monitoring started. I'll track power usage and optimization opportunities."
        }

    if 'stop' in query_lower and 'monitor' in query_lower:
        energy_monitor.stop_monitoring()
        return {
            'action': 'stop_monitoring',
            'reply': "Energy monitoring stopped."
        }

    if 'status' in query_lower or 'current' in query_lower:
        stats = energy_monitor.get_current_stats()
        if stats:
            reply = f"Current power usage: {stats['power_estimate']['total_watts']:.1f}W"
            reply += f" | CPU: {stats['cpu']['percent']:.1f}% | Memory: {stats['memory']['percent']:.1f}%"
            return {'action': 'energy_status', 'reply': reply}
        else:
            return {'action': 'energy_status', 'reply': "No energy data available. Start monitoring first."}

    if 'report' in query_lower or 'summary' in query_lower:
        report = energy_monitor.get_energy_report()
        return {'action': 'energy_report', 'reply': report}

    if 'optimize' in query_lower or 'suggestion' in query_lower:
        suggestions = energy_monitor.get_optimization_suggestions()
        if suggestions:
            reply = f"Found {len(suggestions)} optimization opportunity:\n"
            for suggestion in suggestions:
                reply += f"- {suggestion['message']}: {suggestion['suggestion']}\n"
            return {'action': 'energy_optimize', 'reply': reply}
        else:
            return {'action': 'energy_optimize', 'reply': "No optimization opportunities detected. System is running efficiently!"}

    if 'export' in query_lower:
        result = energy_monitor.export_data()
        return {'action': 'energy_export', 'reply': result}

    return None


def is_energy_request(query: str) -> bool:
    """Check if query is energy-related"""
    keywords = ['energy', 'power', 'battery', 'electricity', 'consumption', 'monitor']
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in keywords)