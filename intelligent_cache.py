"""
Intelligent Caching System for Kora AI Assistant
Provides smart caching for LLM responses, API calls, and frequently accessed data
"""

import hashlib
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import pickle
import os


class CacheStrategy(Enum):
    LRU = "least_recently_used"
    LFU = "least_frequently_used"
    FIFO = "first_in_first_out"
    TTL = "time_to_live"


class CacheEntry:
    def __init__(self, key: str, value: Any, ttl: int = None):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0
        self.ttl = ttl  # Time to live in seconds
        self.size = self._calculate_size()

    def _calculate_size(self) -> int:
        """Estimate size of cached value in bytes"""
        try:
            return len(pickle.dumps(self.value))
        except Exception:
            return len(str(self.value))

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """Update last accessed time and increment access count"""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict:
        """Convert cache entry to dictionary"""
        return {
            'key': self.key,
            'created_at': datetime.fromtimestamp(self.created_at).isoformat(),
            'last_accessed': datetime.fromtimestamp(self.last_accessed).isoformat(),
            'access_count': self.access_count,
            'ttl': self.ttl,
            'size_bytes': self.size,
            'is_expired': self.is_expired()
        }


class IntelligentCache:
    def __init__(self, max_size_mb: int = 100, default_ttl: int = 3600,
                 strategy: CacheStrategy = CacheStrategy.LRU):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.strategy = strategy
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size_bytes': 0
        }

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key from function arguments"""
        key_data = {
            'prefix': prefix,
            'args': str(args),
            'kwargs': str(sorted(kwargs.items()))
        }
        key_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self.lock:
            if key not in self.cache:
                self.stats['misses'] += 1
                return None

            entry = self.cache[key]

            if entry.is_expired():
                self._remove_entry(key)
                self.stats['misses'] += 1
                return None

            entry.touch()
            self.stats['hits'] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        with self.lock:
            # Remove existing entry if present
            if key in self.cache:
                self._remove_entry(key)

            # Create new entry
            ttl = ttl if ttl is not None else self.default_ttl
            entry = CacheEntry(key, value, ttl)

            # Check if we need to evict entries
            while (self.stats['size_bytes'] + entry.size > self.max_size_bytes and
                   self.cache):
                self._evict_entry()

            # Add new entry
            self.cache[key] = entry
            self.stats['size_bytes'] += entry.size
            return True

    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self.lock:
            if key in self.cache:
                self._remove_entry(key)
                return True
            return False

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.stats['size_bytes'] = 0

    def _remove_entry(self, key: str):
        """Remove entry from cache and update stats"""
        if key in self.cache:
            entry = self.cache[key]
            self.stats['size_bytes'] -= entry.size
            del self.cache[key]

    def _evict_entry(self):
        """Evict an entry based on cache strategy"""
        if not self.cache:
            return

        if self.strategy == CacheStrategy.LRU:
            # Evict least recently used
            key_to_evict = min(self.cache.keys(),
                             key=lambda k: self.cache[k].last_accessed)
        elif self.strategy == CacheStrategy.LFU:
            # Evict least frequently used
            key_to_evict = min(self.cache.keys(),
                             key=lambda k: self.cache[k].access_count)
        elif self.strategy == CacheStrategy.FIFO:
            # Evict oldest entry
            key_to_evict = min(self.cache.keys(),
                             key=lambda k: self.cache[k].created_at)
        elif self.strategy == CacheStrategy.TTL:
            # Evict expired entries first, then oldest
            expired_keys = [k for k in self.cache.keys() if self.cache[k].is_expired()]
            if expired_keys:
                key_to_evict = expired_keys[0]
            else:
                key_to_evict = min(self.cache.keys(),
                                 key=lambda k: self.cache[k].created_at)
        else:
            # Default to LRU
            key_to_evict = min(self.cache.keys(),
                             key=lambda k: self.cache[k].last_accessed)

        self._remove_entry(key_to_evict)
        self.stats['evictions'] += 1

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self.lock:
            hit_rate = (self.stats['hits'] /
                       max(1, self.stats['hits'] + self.stats['misses'])) * 100

            return {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate_percent': round(hit_rate, 2),
                'evictions': self.stats['evictions'],
                'entries_count': len(self.cache),
                'size_bytes': self.stats['size_bytes'],
                'size_mb': round(self.stats['size_bytes'] / (1024 * 1024), 2),
                'max_size_mb': round(self.max_size_bytes / (1024 * 1024), 2),
                'strategy': self.strategy.value
            }

    def get_entries_info(self, limit: int = 20) -> List[Dict]:
        """Get information about cache entries"""
        with self.lock:
            entries = list(self.cache.values())
            # Sort by last accessed time
            entries.sort(key=lambda e: e.last_accessed, reverse=True)

            return [entry.to_dict() for entry in entries[:limit]]

    def cleanup_expired(self):
        """Remove all expired entries"""
        with self.lock:
            expired_keys = [k for k in self.cache.keys() if self.cache[k].is_expired()]
            for key in expired_keys:
                self._remove_entry(key)
            return len(expired_keys)

    def optimize(self):
        """Optimize cache by removing expired and least useful entries"""
        with self.lock:
            # Remove expired entries
            expired_count = self.cleanup_expired()

            # If still over size limit, evict more entries
            evicted_count = 0
            while self.stats['size_bytes'] > self.max_size_bytes * 0.9 and self.cache:
                self._evict_entry()
                evicted_count += 1

            return {
                'expired_removed': expired_count,
                'entries_evicted': evicted_count,
                'total_freed': expired_count + evicted_count
            }


class CacheManager:
    def __init__(self):
        self.caches: Dict[str, IntelligentCache] = {}
        self.lock = threading.Lock()

        # Initialize default caches
        self._create_cache('llm_responses', max_size_mb=50, ttl=7200)  # 2 hours
        self._create_cache('api_responses', max_size_mb=30, ttl=3600)  # 1 hour
        self._create_cache('file_contents', max_size_mb=20, ttl=1800)  # 30 minutes
        self._create_cache('user_data', max_size_mb=10, ttl=86400)    # 24 hours

    def _create_cache(self, name: str, max_size_mb: int = 100,
                     ttl: int = 3600, strategy: CacheStrategy = CacheStrategy.LRU):
        """Create a new cache instance"""
        with self.lock:
            if name not in self.caches:
                self.caches[name] = IntelligentCache(max_size_mb, ttl, strategy)

    def get_cache(self, name: str) -> Optional[IntelligentCache]:
        """Get a specific cache by name"""
        with self.lock:
            return self.caches.get(name)

    def cache_function_result(self, cache_name: str, ttl: int = None):
        """Decorator to cache function results"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                cache = self.get_cache(cache_name)
                if not cache:
                    return func(*args, **kwargs)

                # Generate cache key
                key = cache._generate_key(func.__name__, *args, **kwargs)

                # Try to get from cache
                result = cache.get(key)
                if result is not None:
                    return result

                # Execute function and cache result
                result = func(*args, **kwargs)
                cache.set(key, result, ttl)
                return result
            return wrapper
        return decorator

    def get_all_stats(self) -> Dict:
        """Get statistics for all caches"""
        with self.lock:
            stats = {}
            for name, cache in self.caches.items():
                stats[name] = cache.get_stats()
            return stats

    def cleanup_all(self):
        """Cleanup all caches"""
        with self.lock:
            total_removed = 0
            for cache in self.caches.values():
                total_removed += cache.cleanup_expired()
            return total_removed

    def optimize_all(self):
        """Optimize all caches"""
        with self.lock:
            results = {}
            for name, cache in self.caches.items():
                results[name] = cache.optimize()
            return results

    def clear_all(self):
        """Clear all caches"""
        with self.lock:
            for cache in self.caches.values():
                cache.clear()

    def export_cache_data(self, cache_name: str = None, filename: str = None):
        """Export cache data to JSON file"""
        if filename is None:
            filename = f"cache_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with self.lock:
            if cache_name and cache_name in self.caches:
                data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'cache_name': cache_name,
                    'stats': self.caches[cache_name].get_stats(),
                    'entries': self.caches[cache_name].get_entries_info(100)
                }
            else:
                data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'all_stats': self.get_all_stats(),
                    'caches': {}
                }
                for name, cache in self.caches.items():
                    data['caches'][name] = {
                        'stats': cache.get_stats(),
                        'entries': cache.get_entries_info(50)
                    }

        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            return f"Cache data exported to {filename}"
        except Exception as e:
            return f"Failed to export cache data: {e}"

    def get_cache_report(self) -> str:
        """Generate comprehensive cache report"""
        all_stats = self.get_all_stats()

        report = []
        report.append("💾 INTELLIGENT CACHE REPORT")
        report.append("=" * 40)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Overall Statistics
        total_hits = sum(stats['hits'] for stats in all_stats.values())
        total_misses = sum(stats['misses'] for stats in all_stats.values())
        total_hit_rate = (total_hits / max(1, total_hits + total_misses)) * 100

        report.append("📊 OVERALL STATISTICS")
        report.append("-" * 25)
        report.append(f"Total Cache Hits: {total_hits}")
        report.append(f"Total Cache Misses: {total_misses}")
        report.append(f"Overall Hit Rate: {total_hit_rate:.2f}%")
        report.append("")

        # Per-Cache Statistics
        report.append("📈 PER-CACHE STATISTICS")
        report.append("-" * 30)
        for cache_name, stats in all_stats.items():
            report.append(f"\n{cache_name.upper()}:")
            report.append(f"  Entries: {stats['entries_count']}")
            report.append(f"  Size: {stats['size_mb']:.2f} MB / {stats['max_size_mb']:.2f} MB")
            report.append(f"  Hit Rate: {stats['hit_rate_percent']:.2f}%")
            report.append(f"  Evictions: {stats['evictions']}")
            report.append(f"  Strategy: {stats['strategy']}")

        # Top Entries
        report.append("\n🔝 TOP CACHED ENTRIES")
        report.append("-" * 25)
        for cache_name, cache in self.caches.items():
            entries = cache.get_entries_info(5)
            if entries:
                report.append(f"\n{cache_name.upper()}:")
                for i, entry in enumerate(entries, 1):
                    key_preview = entry['key'][:50] + "..." if len(entry['key']) > 50 else entry['key']
                    report.append(f"  {i}. {key_preview}")
                    report.append(f"     Accesses: {entry['access_count']}, Size: {entry['size_bytes']} bytes")

        return "\n".join(report)


# Global instance
cache_manager = CacheManager()


def handle_cache_command(query: str) -> Dict:
    """Handle cache-related commands"""
    query_lower = query.lower()

    if 'status' in query_lower or 'stats' in query_lower:
        all_stats = cache_manager.get_all_stats()
        reply = "Cache Status:\n"
        for cache_name, stats in all_stats.items():
            reply += f"\n{cache_name}:\n"
            reply += f"  Hit Rate: {stats['hit_rate_percent']:.2f}%\n"
            reply += f"  Size: {stats['size_mb']:.2f} MB\n"
            reply += f"  Entries: {stats['entries_count']}\n"
        return {'action': 'cache_status', 'reply': reply}

    if 'report' in query_lower or 'summary' in query_lower:
        report = cache_manager.get_cache_report()
        return {'action': 'cache_report', 'reply': report}

    if 'clear' in query_lower:
        if 'llm' in query_lower:
            cache_manager.get_cache('llm_responses').clear()
            return {'action': 'clear_cache', 'reply': 'LLM response cache cleared.'}
        elif 'api' in query_lower:
            cache_manager.get_cache('api_responses').clear()
            return {'action': 'clear_cache', 'reply': 'API response cache cleared.'}
        elif 'all' in query_lower:
            cache_manager.clear_all()
            return {'action': 'clear_cache', 'reply': 'All caches cleared.'}
        else:
            return {'action': 'clear_cache', 'reply': 'Please specify which cache to clear (llm, api, or all).'}

    if 'optimize' in query_lower:
        results = cache_manager.optimize_all()
        reply = "Cache optimization completed:\n"
        for cache_name, result in results.items():
            reply += f"{cache_name}: {result['total_freed']} entries freed\n"
        return {'action': 'optimize_cache', 'reply': reply}

    if 'export' in query_lower:
        result = cache_manager.export_cache_data()
        return {'action': 'export_cache', 'reply': result}

    if 'cleanup' in query_lower:
        removed = cache_manager.cleanup_all()
        return {'action': 'cleanup_cache', 'reply': f'Cleaned up {removed} expired cache entries.'}

    return None


def is_cache_request(query: str) -> bool:
    """Check if query is cache-related"""
    keywords = ['cache', 'caching', 'performance', 'optimize', 'speed']
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in keywords)


# Convenience decorators for common use cases
def cache_llm_response(ttl: int = 7200):
    """Decorator to cache LLM responses"""
    return cache_manager.cache_function_result('llm_responses', ttl)


def cache_api_response(ttl: int = 3600):
    """Decorator to cache API responses"""
    return cache_manager.cache_function_result('api_responses', ttl)


def cache_file_content(ttl: int = 1800):
    """Decorator to cache file contents"""
    return cache_manager.cache_function_result('file_contents', ttl)


def cache_user_data(ttl: int = 86400):
    """Decorator to cache user data"""
    return cache_manager.cache_function_result('user_data', ttl)