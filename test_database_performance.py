"""
Test Database Performance Optimizations

This module tests the database performance optimizations including connection pooling,
indexes, and query optimization services.
"""

import pytest
import time
from datetime import datetime, date, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

from database.db import engine
from database.table import (
    Base, User, UserDetail, DenseReport, Comment, UserType, ReportStatus
)
from services.query_optimization_service import QueryOptimizationService
from services.database_performance_service import DatabasePerformanceService


class TestDatabasePerformance:
    """Test database performance optimizations"""
    
    @classmethod
    def setup_class(cls):
        """Set up test database and sample data"""
        # Create test session
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Create sample data for testing
        cls.setup_sample_data()
    
    @classmethod
    def setup_sample_data(cls):
        """Create sample data for performance testing"""
        db = cls.SessionLocal()
        try:
            # Create test users
            for i in range(100):
                user = User(
                    id=f"test_user_{i}",
                    password="hashed_password",
                    type=UserType.Patient if i % 2 == 0 else UserType.Doctor,
                    is_active=True,
                    created_at=datetime.now() - timedelta(days=i)
                )
                db.add(user)
                
                # Add user details
                user_detail = UserDetail(
                    id=f"test_user_{i}",
                    name=f"Test User {i}",
                    phone=f"123456789{i:02d}",
                    email=f"test{i}@example.com"
                )
                db.add(user_detail)
            
            # Create test reports
            for i in range(500):
                report = DenseReport(
                    user=f"test_user_{i % 50}",  # Patient users
                    doctor=f"test_user_{50 + (i % 50)}",  # Doctor users
                    submitTime=date.today() - timedelta(days=i % 365),
                    current_status=ReportStatus(i % 4),
                    diagnose=f"Test diagnosis {i}"
                )
                db.add(report)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            print(f"Error setting up sample data: {e}")
        finally:
            db.close()
    
    def test_connection_pool_configuration(self):
        """Test that connection pooling is properly configured"""
        # Check that the engine has the correct pool configuration
        assert engine.pool.size() == 20
        assert engine.pool._max_overflow == 30
        assert engine.pool._pre_ping is True
        assert engine.pool._recycle == 3600
    
    def test_database_indexes_exist(self):
        """Test that performance indexes are created"""
        db = self.SessionLocal()
        try:
            # Check for indexes on user table
            user_indexes = db.execute(text("""
                SELECT index_name 
                FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user'
                AND index_name LIKE 'idx_%'
            """)).fetchall()
            
            index_names = [row[0] for row in user_indexes]
            assert 'idx_user_type_active' in index_names
            assert 'idx_user_last_login' in index_names
            assert 'idx_user_created_at' in index_names
            
            # Check for indexes on dense_report table
            report_indexes = db.execute(text("""
                SELECT index_name 
                FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND table_name = 'dense_report'
                AND index_name LIKE 'idx_%'
            """)).fetchall()
            
            report_index_names = [row[0] for row in report_indexes]
            assert 'idx_report_user_status' in report_index_names
            assert 'idx_report_doctor_status' in report_index_names
            assert 'idx_report_submit_time' in report_index_names
            
        finally:
            db.close()
    
    def test_query_optimization_service_pagination(self):
        """Test paginated query performance"""
        db = self.SessionLocal()
        try:
            start_time = time.time()
            
            # Test paginated reports query
            result = QueryOptimizationService.get_paginated_reports(
                db=db,
                page=1,
                page_size=20,
                sort_by='submitTime',
                sort_order='desc'
            )
            
            execution_time = time.time() - start_time
            
            # Verify results
            assert 'reports' in result
            assert 'pagination' in result
            assert len(result['reports']) <= 20
            assert result['pagination']['page'] == 1
            assert result['pagination']['page_size'] == 20
            
            # Performance check - should be fast with indexes
            assert execution_time < 1.0, f"Query took {execution_time:.2f}s, expected < 1.0s"
            
        finally:
            db.close()
    
    def test_query_optimization_service_statistics(self):
        """Test report statistics query performance"""
        db = self.SessionLocal()
        try:
            start_time = time.time()
            
            # Test statistics query
            result = QueryOptimizationService.get_report_statistics(db=db)
            
            execution_time = time.time() - start_time
            
            # Verify results
            assert 'status_distribution' in result
            assert 'monthly_trends' in result
            assert 'total_reports' in result
            assert isinstance(result['total_reports'], int)
            
            # Performance check
            assert execution_time < 1.0, f"Statistics query took {execution_time:.2f}s, expected < 1.0s"
            
        finally:
            db.close()
    
    def test_query_optimization_service_search(self):
        """Test search functionality performance"""
        db = self.SessionLocal()
        try:
            start_time = time.time()
            
            # Test search query
            result = QueryOptimizationService.search_reports(
                db=db,
                search_term="Test",
                page=1,
                page_size=10
            )
            
            execution_time = time.time() - start_time
            
            # Verify results
            assert 'reports' in result
            assert 'search_term' in result
            assert 'pagination' in result
            assert result['search_term'] == "Test"
            
            # Performance check
            assert execution_time < 2.0, f"Search query took {execution_time:.2f}s, expected < 2.0s"
            
        finally:
            db.close()
    
    def test_bulk_operations_performance(self):
        """Test bulk operations performance"""
        db = self.SessionLocal()
        try:
            # Create test admin user for audit logging
            admin_user = User(
                id="test_admin",
                password="hashed_password",
                type=UserType.Doctor,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            
            # Get some report IDs for bulk update
            reports = db.query(DenseReport).limit(10).all()
            report_ids = [str(report.id) for report in reports]
            
            start_time = time.time()
            
            # Test bulk update
            result = QueryOptimizationService.bulk_update_report_status(
                db=db,
                report_ids=report_ids,
                new_status=ReportStatus.Completed,
                updated_by="test_admin"
            )
            
            execution_time = time.time() - start_time
            
            # Verify results
            assert result['success'] is True
            assert result['updated_count'] == len(report_ids)
            
            # Performance check - bulk operations should be fast
            assert execution_time < 1.0, f"Bulk update took {execution_time:.2f}s, expected < 1.0s"
            
            # Clean up admin user
            db.query(User).filter(User.id == "test_admin").delete()
            db.commit()
            
        finally:
            db.close()
    
    def test_database_performance_monitoring(self):
        """Test database performance monitoring service"""
        db = self.SessionLocal()
        monitor = DatabasePerformanceService()
        
        try:
            # Test query monitoring
            with monitor.monitor_query("test_query", db):
                # Simulate a query
                db.execute(text("SELECT COUNT(*) FROM user")).scalar()
            
            # Check that stats were recorded
            stats = monitor.get_query_statistics()
            assert 'query_stats' in stats
            assert 'test_query' in stats['query_stats']
            assert stats['query_stats']['test_query']['count'] == 1
            
            # Test performance analysis
            analysis = monitor.analyze_database_performance(db)
            assert 'connection_pool' in analysis
            assert 'table_sizes' in analysis
            
            # Test health check
            health = monitor.get_database_health_check(db)
            assert 'status' in health
            assert 'connectivity' in health
            assert health['connectivity'] == 'ok'
            
        finally:
            db.close()
    
    def test_concurrent_connections(self):
        """Test that connection pooling handles concurrent connections"""
        import threading
        import concurrent.futures
        
        def query_database():
            """Function to run in separate thread"""
            db = self.SessionLocal()
            try:
                result = db.execute(text("SELECT COUNT(*) FROM user")).scalar()
                return result
            finally:
                db.close()
        
        # Test concurrent connections
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(query_database) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All queries should succeed
        assert len(results) == 10
        assert all(isinstance(result, int) for result in results)
    
    def test_query_performance_with_indexes(self):
        """Test that queries perform better with indexes"""
        db = self.SessionLocal()
        try:
            # Test query that should benefit from indexes
            start_time = time.time()
            
            # Query using indexed columns
            result = db.query(DenseReport).filter(
                DenseReport.current_status == ReportStatus.Checking
            ).order_by(DenseReport.submitTime.desc()).limit(10).all()
            
            execution_time = time.time() - start_time
            
            # Should be fast with proper indexes
            assert execution_time < 0.5, f"Indexed query took {execution_time:.2f}s, expected < 0.5s"
            assert len(result) <= 10
            
            # Test another indexed query
            start_time = time.time()
            
            result = db.query(User).filter(
                User.type == UserType.Doctor,
                User.is_active == True
            ).limit(10).all()
            
            execution_time = time.time() - start_time
            
            # Should be fast with composite index
            assert execution_time < 0.5, f"Composite indexed query took {execution_time:.2f}s, expected < 0.5s"
            
        finally:
            db.close()
    
    @classmethod
    def teardown_class(cls):
        """Clean up test data"""
        db = cls.SessionLocal()
        try:
            # Clean up test data
            db.query(Comment).filter(Comment.user.like('test_user_%')).delete(synchronize_session=False)
            db.query(DenseReport).filter(DenseReport.user.like('test_user_%')).delete(synchronize_session=False)
            db.query(UserDetail).filter(UserDetail.id.like('test_user_%')).delete(synchronize_session=False)
            db.query(User).filter(User.id.like('test_user_%')).delete(synchronize_session=False)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error cleaning up test data: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    # Run basic performance tests
    test_instance = TestDatabasePerformance()
    test_instance.setup_class()
    
    try:
        print("Testing connection pool configuration...")
        test_instance.test_connection_pool_configuration()
        print("✓ Connection pool test passed")
        
        print("Testing database indexes...")
        test_instance.test_database_indexes_exist()
        print("✓ Database indexes test passed")
        
        print("Testing query optimization service...")
        test_instance.test_query_optimization_service_pagination()
        print("✓ Pagination test passed")
        
        test_instance.test_query_optimization_service_statistics()
        print("✓ Statistics test passed")
        
        test_instance.test_query_optimization_service_search()
        print("✓ Search test passed")
        
        print("Testing bulk operations...")
        test_instance.test_bulk_operations_performance()
        print("✓ Bulk operations test passed")
        
        print("Testing performance monitoring...")
        test_instance.test_database_performance_monitoring()
        print("✓ Performance monitoring test passed")
        
        print("Testing concurrent connections...")
        test_instance.test_concurrent_connections()
        print("✓ Concurrent connections test passed")
        
        print("Testing query performance with indexes...")
        test_instance.test_query_performance_with_indexes()
        print("✓ Query performance test passed")
        
        print("\n✅ All database performance tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        test_instance.teardown_class()