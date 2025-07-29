"""
Database Performance Monitoring Service

This module provides database performance monitoring, query analysis, and optimization recommendations.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timedelta
import time
import json
import logging
from contextlib import contextmanager

from dense_platform_backend_main.database.table import AuditLog


class DatabasePerformanceService:
    """Service for monitoring and optimizing database performance"""
    
    def __init__(self):
        self.query_stats = {}
        self.slow_query_threshold = 1.0  # seconds
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def monitor_query(self, query_name: str, db: Session):
        """
        Context manager to monitor query performance
        
        Args:
            query_name: Name/identifier for the query
            db: Database session
        """
        start_time = time.time()
        try:
            yield
        finally:
            execution_time = time.time() - start_time
            self._record_query_stats(query_name, execution_time)
            
            if execution_time > self.slow_query_threshold:
                self.logger.warning(f"Slow query detected: {query_name} took {execution_time:.2f}s")
                self._log_slow_query(db, query_name, execution_time)
    
    def _record_query_stats(self, query_name: str, execution_time: float):
        """Record query statistics for analysis"""
        if query_name not in self.query_stats:
            self.query_stats[query_name] = {
                'count': 0,
                'total_time': 0,
                'min_time': float('inf'),
                'max_time': 0,
                'avg_time': 0
            }
        
        stats = self.query_stats[query_name]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['avg_time'] = stats['total_time'] / stats['count']
    
    def _log_slow_query(self, db: Session, query_name: str, execution_time: float):
        """Log slow query to audit log"""
        try:
            audit_log = AuditLog(
                user_id=None,
                action='slow_query_detected',
                resource_type='database',
                resource_id=query_name,
                new_values=json.dumps({
                    'execution_time': execution_time,
                    'threshold': self.slow_query_threshold
                }),
                timestamp=datetime.now(),
                success=True
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            self.logger.error(f"Failed to log slow query: {e}")
    
    def get_query_statistics(self) -> Dict[str, Any]:
        """
        Get current query statistics
        
        Returns:
            Dictionary with query performance statistics
        """
        return {
            'query_stats': self.query_stats,
            'slow_query_threshold': self.slow_query_threshold,
            'total_queries': sum(stats['count'] for stats in self.query_stats.values()),
            'slowest_queries': sorted(
                [(name, stats['max_time']) for name, stats in self.query_stats.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def analyze_database_performance(self, db: Session) -> Dict[str, Any]:
        """
        Analyze overall database performance
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with performance analysis
        """
        try:
            analysis = {}
            
            # Check connection pool status
            engine = db.get_bind()
            pool = engine.pool
            analysis['connection_pool'] = {
                'size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow()
            }
            
            # Check table sizes
            table_sizes = self._get_table_sizes(db)
            analysis['table_sizes'] = table_sizes
            
            # Check index usage (MySQL specific)
            index_usage = self._get_index_usage(db)
            analysis['index_usage'] = index_usage
            
            # Check slow queries from performance schema
            slow_queries = self._get_slow_queries_from_db(db)
            analysis['slow_queries'] = slow_queries
            
            # Generate recommendations
            recommendations = self._generate_recommendations(analysis)
            analysis['recommendations'] = recommendations
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing database performance: {e}")
            return {'error': str(e)}
    
    def _get_table_sizes(self, db: Session) -> Dict[str, Any]:
        """Get table sizes and row counts"""
        try:
            query = text("""
                SELECT 
                    table_name,
                    table_rows,
                    data_length,
                    index_length,
                    (data_length + index_length) as total_size
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                ORDER BY total_size DESC
            """)
            
            result = db.execute(query).fetchall()
            
            return [
                {
                    'table_name': row[0],
                    'row_count': row[1],
                    'data_size': row[2],
                    'index_size': row[3],
                    'total_size': row[4]
                }
                for row in result
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting table sizes: {e}")
            return []
    
    def _get_index_usage(self, db: Session) -> Dict[str, Any]:
        """Get index usage statistics"""
        try:
            query = text("""
                SELECT 
                    table_name,
                    index_name,
                    cardinality,
                    non_unique
                FROM information_schema.statistics 
                WHERE table_schema = DATABASE()
                ORDER BY table_name, cardinality DESC
            """)
            
            result = db.execute(query).fetchall()
            
            return [
                {
                    'table_name': row[0],
                    'index_name': row[1],
                    'cardinality': row[2],
                    'non_unique': row[3]
                }
                for row in result
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting index usage: {e}")
            return []
    
    def _get_slow_queries_from_db(self, db: Session) -> List[Dict[str, Any]]:
        """Get slow queries from performance schema (if available)"""
        try:
            # Check if performance schema is available
            check_query = text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'performance_schema' 
                AND table_name = 'events_statements_summary_by_digest'
            """)
            
            if db.execute(check_query).scalar() == 0:
                return []
            
            query = text("""
                SELECT 
                    DIGEST_TEXT,
                    COUNT_STAR,
                    AVG_TIMER_WAIT/1000000000 as avg_time_seconds,
                    MAX_TIMER_WAIT/1000000000 as max_time_seconds
                FROM performance_schema.events_statements_summary_by_digest 
                WHERE DIGEST_TEXT IS NOT NULL
                ORDER BY AVG_TIMER_WAIT DESC 
                LIMIT 10
            """)
            
            result = db.execute(query).fetchall()
            
            return [
                {
                    'query': row[0][:200] + '...' if len(row[0]) > 200 else row[0],
                    'execution_count': row[1],
                    'avg_time': row[2],
                    'max_time': row[3]
                }
                for row in result
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting slow queries from database: {e}")
            return []
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # Check connection pool
        pool_info = analysis.get('connection_pool', {})
        if pool_info.get('checked_out', 0) > pool_info.get('size', 0) * 0.8:
            recommendations.append("Consider increasing connection pool size - high utilization detected")
        
        # Check table sizes
        table_sizes = analysis.get('table_sizes', [])
        for table in table_sizes[:3]:  # Top 3 largest tables
            if table['row_count'] > 100000:
                recommendations.append(f"Table {table['table_name']} has {table['row_count']} rows - consider partitioning or archiving")
        
        # Check for missing indexes
        slow_queries = analysis.get('slow_queries', [])
        if slow_queries:
            recommendations.append("Slow queries detected - review query patterns and consider adding indexes")
        
        # Check index usage
        index_usage = analysis.get('index_usage', [])
        unused_indexes = [idx for idx in index_usage if idx['cardinality'] == 0]
        if unused_indexes:
            recommendations.append(f"Found {len(unused_indexes)} potentially unused indexes - consider removing them")
        
        return recommendations
    
    def optimize_table_maintenance(self, db: Session, table_name: str) -> Dict[str, Any]:
        """
        Perform table maintenance operations
        
        Args:
            db: Database session
            table_name: Name of table to optimize
            
        Returns:
            Dictionary with maintenance results
        """
        try:
            results = {}
            
            # Analyze table
            analyze_query = text(f"ANALYZE TABLE {table_name}")
            analyze_result = db.execute(analyze_query).fetchall()
            results['analyze'] = [dict(row) for row in analyze_result]
            
            # Optimize table
            optimize_query = text(f"OPTIMIZE TABLE {table_name}")
            optimize_result = db.execute(optimize_query).fetchall()
            results['optimize'] = [dict(row) for row in optimize_result]
            
            return {
                'success': True,
                'table_name': table_name,
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Error optimizing table {table_name}: {e}")
            return {
                'success': False,
                'table_name': table_name,
                'error': str(e)
            }
    
    def get_database_health_check(self, db: Session) -> Dict[str, Any]:
        """
        Perform comprehensive database health check
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with health check results
        """
        try:
            health_check = {
                'timestamp': datetime.now().isoformat(),
                'status': 'healthy',
                'issues': []
            }
            
            # Check database connectivity
            try:
                db.execute(text("SELECT 1")).scalar()
                health_check['connectivity'] = 'ok'
            except Exception as e:
                health_check['connectivity'] = 'failed'
                health_check['issues'].append(f"Database connectivity issue: {e}")
                health_check['status'] = 'unhealthy'
            
            # Check disk space (if possible)
            try:
                disk_query = text("""
                    SELECT 
                        SUM(data_length + index_length) / 1024 / 1024 as db_size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                """)
                db_size = db.execute(disk_query).scalar()
                health_check['database_size_mb'] = float(db_size) if db_size else 0
            except Exception as e:
                health_check['issues'].append(f"Could not determine database size: {e}")
            
            # Check for long-running queries
            try:
                long_queries = text("""
                    SELECT COUNT(*) 
                    FROM information_schema.processlist 
                    WHERE command != 'Sleep' AND time > 30
                """)
                long_query_count = db.execute(long_queries).scalar()
                if long_query_count > 0:
                    health_check['issues'].append(f"{long_query_count} long-running queries detected")
                    health_check['status'] = 'warning'
            except Exception:
                pass  # Not critical if this fails
            
            # Check connection count
            try:
                connection_query = text("SHOW STATUS LIKE 'Threads_connected'")
                result = db.execute(connection_query).fetchone()
                if result:
                    connection_count = int(result[1])
                    health_check['active_connections'] = connection_count
                    if connection_count > 100:  # Arbitrary threshold
                        health_check['issues'].append(f"High connection count: {connection_count}")
                        health_check['status'] = 'warning'
            except Exception:
                pass  # Not critical if this fails
            
            return health_check
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }


    def analyze_query_performance(self, db: Session, query) -> Dict[str, Any]:
        """
        Analyze performance of a specific query
        
        Args:
            db: Database session
            query: SQLAlchemy query object
            
        Returns:
            Dictionary with query performance analysis
        """
        try:
            start_time = time.time()
            
            # Execute the query to measure performance
            result = query.all()
            execution_time = time.time() - start_time
            
            # Get query string for analysis
            query_str = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
            
            analysis = {
                'query': query_str[:200] + '...' if len(query_str) > 200 else query_str,
                'execution_time': execution_time,
                'result_count': len(result),
                'is_slow': execution_time > self.slow_query_threshold,
                'recommendations': []
            }
            
            # Add recommendations based on analysis
            if execution_time > self.slow_query_threshold:
                analysis['recommendations'].append("Query execution time exceeds threshold - consider optimization")
            
            if len(result) > 1000:
                analysis['recommendations'].append("Large result set - consider pagination or filtering")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing query performance: {e}")
            return {'error': str(e)}
    
    def get_slow_queries(self, db: Session, threshold_ms: int = 1000) -> List[Dict[str, Any]]:
        """
        Get slow queries from monitoring data
        
        Args:
            db: Database session
            threshold_ms: Threshold in milliseconds
            
        Returns:
            List of slow queries
        """
        threshold_seconds = threshold_ms / 1000.0
        
        slow_queries = []
        for query_name, stats in self.query_stats.items():
            if stats['max_time'] > threshold_seconds:
                slow_queries.append({
                    'query_name': query_name,
                    'max_time': stats['max_time'],
                    'avg_time': stats['avg_time'],
                    'execution_count': stats['count']
                })
        
        # Sort by max execution time
        slow_queries.sort(key=lambda x: x['max_time'], reverse=True)
        
        return slow_queries
    
    def optimize_table_indexes(self, db: Session, table_name: str) -> Dict[str, Any]:
        """
        Provide index optimization suggestions for a table
        
        Args:
            db: Database session
            table_name: Name of the table to optimize
            
        Returns:
            Dictionary with optimization suggestions
        """
        try:
            suggestions = {
                'table_name': table_name,
                'current_indexes': [],
                'suggested_indexes': [],
                'optimization_notes': []
            }
            
            # Get current indexes
            try:
                index_query = text(f"""
                    SELECT index_name, column_name, non_unique
                    FROM information_schema.statistics 
                    WHERE table_schema = DATABASE() 
                    AND table_name = '{table_name}'
                    ORDER BY index_name, seq_in_index
                """)
                
                indexes = db.execute(index_query).fetchall()
                suggestions['current_indexes'] = [
                    {
                        'index_name': row[0],
                        'column_name': row[1],
                        'non_unique': bool(row[2])
                    }
                    for row in indexes
                ]
                
            except Exception:
                # Fallback for SQLite or other databases
                suggestions['optimization_notes'].append("Could not retrieve current indexes - database may not support information_schema")
            
            # Add generic optimization suggestions based on table name
            if table_name == 'user':
                suggestions['suggested_indexes'].extend([
                    "CREATE INDEX idx_user_type_active ON user(type, is_active)",
                    "CREATE INDEX idx_user_created_at ON user(created_at)"
                ])
            elif table_name == 'dense_report':
                suggestions['suggested_indexes'].extend([
                    "CREATE INDEX idx_report_user_status ON dense_report(user, current_status)",
                    "CREATE INDEX idx_report_submit_time ON dense_report(submitTime)"
                ])
            
            suggestions['optimization_notes'].append(f"Consider analyzing query patterns for {table_name} table to identify optimal indexes")
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Error optimizing table indexes for {table_name}: {e}")
            return {
                'table_name': table_name,
                'error': str(e)
            }


# Global instance for monitoring
db_performance_monitor = DatabasePerformanceService()