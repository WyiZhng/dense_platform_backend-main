#!/usr/bin/env python3
"""
Migration CLI Script

Command-line interface for running data migration from file storage to database.
"""

import argparse
import sys
import os
from datetime import datetime
from migration.migration_manager import MigrationManager


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Migrate data from file storage to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_migration.py --status                    # Check migration status
  python run_migration.py --migrate                   # Run full migration
  python run_migration.py --migrate --storage ./data  # Migrate from custom path
  python run_migration.py --cleanup --confirm         # Clean up file storage
  python run_migration.py --test                      # Run migration tests
        """
    )
    
    parser.add_argument(
        '--storage',
        default='storage',
        help='Path to storage directory (default: storage)'
    )
    
    parser.add_argument(
        '--backup',
        default='storage_backup',
        help='Path to backup directory (default: storage_backup)'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check current migration status'
    )
    
    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Run complete migration process'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Clean up file storage after migration'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm destructive operations (required for cleanup)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run migration tests'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create migration manager
    migration_manager = MigrationManager(
        storage_path=args.storage,
        backup_path=args.backup
    )
    
    try:
        if args.test:
            run_tests()
            return
        
        if args.status:
            check_status(migration_manager)
            return
        
        if args.migrate:
            run_migration(migration_manager)
            return
        
        if args.cleanup:
            run_cleanup(migration_manager, args.confirm)
            return
        
        # If no action specified, show help
        parser.print_help()
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


def check_status(migration_manager: MigrationManager):
    """Check and display migration status"""
    print("Checking migration status...")
    print("=" * 50)
    
    status = migration_manager.get_migration_status()
    
    print(f"Database tables exist: {status['database_tables_exist']}")
    print(f"Data migrated: {status['data_migrated']}")
    print(f"User count: {status['user_count']}")
    print(f"Report count: {status['report_count']}")
    print(f"Image count: {status['image_count']}")
    print(f"File storage exists: {status['file_storage_exists']}")
    print(f"Backup exists: {status['backup_exists']}")
    
    if status['data_migrated']:
        print("\n✅ Migration appears to be completed")
    else:
        print("\n⚠️  No migrated data found")
    
    if status['file_storage_exists'] and status['data_migrated']:
        print("💡 Consider running cleanup to remove old file storage")


def run_migration(migration_manager: MigrationManager):
    """Run the complete migration process"""
    print("Starting complete migration process...")
    print("=" * 50)
    
    # Confirm before proceeding
    response = input("This will migrate all data from files to database. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        return
    
    start_time = datetime.now()
    results = migration_manager.run_complete_migration()
    end_time = datetime.now()
    
    print("\nMigration Results:")
    print("=" * 50)
    print(f"Success: {results['success']}")
    print(f"Duration: {end_time - start_time}")
    print(f"Backup created: {results['backup_created']}")
    
    if results.get('user_migration'):
        user_results = results['user_migration']
        print(f"\nUser Migration:")
        print(f"  Users migrated: {user_results.get('users_migrated', 0)}")
        print(f"  Details migrated: {user_results.get('details_migrated', 0)}")
        print(f"  Doctors migrated: {user_results.get('doctors_migrated', 0)}")
        print(f"  Avatars migrated: {user_results.get('avatars_migrated', 0)}")
    
    if results.get('report_migration'):
        report_results = results['report_migration']
        print(f"\nReport Migration:")
        print(f"  Reports migrated: {report_results.get('reports_migrated', 0)}")
        print(f"  Images migrated: {report_results.get('images_migrated', 0)}")
        print(f"  Dense images migrated: {report_results.get('dense_images_migrated', 0)}")
        print(f"  Comments migrated: {report_results.get('comments_migrated', 0)}")
    
    if results.get('verification'):
        verification = results['verification']
        print(f"\nVerification:")
        print(f"  Valid: {verification.get('valid', False)}")
        if verification.get('issues'):
            print(f"  Issues: {len(verification['issues'])}")
            for issue in verification['issues'][:5]:  # Show first 5 issues
                print(f"    - {issue}")
    
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")
    
    if results['success']:
        print("\n✅ Migration completed successfully!")
        print("💡 You can now run --cleanup --confirm to remove old file storage")
    else:
        print("\n❌ Migration failed!")
        print("💡 Check the errors above and fix any issues before retrying")


def run_cleanup(migration_manager: MigrationManager, confirm: bool):
    """Run file storage cleanup"""
    print("File storage cleanup...")
    print("=" * 50)
    
    if not confirm:
        print("❌ Cleanup requires --confirm flag to proceed")
        print("This is a destructive operation that will remove file storage")
        return
    
    # Double confirmation for safety
    response = input("This will permanently delete file storage. Are you sure? (y/N): ")
    if response.lower() != 'y':
        print("Cleanup cancelled")
        return
    
    results = migration_manager.cleanup_file_storage(confirm=True)
    
    print(f"Success: {results['success']}")
    print(f"Files removed: {results['files_removed']}")
    print(f"Directories removed: {results['directories_removed']}")
    
    if results['errors']:
        print(f"Errors: {results['errors']}")
    
    if results['success']:
        print("\n✅ Cleanup completed successfully!")
    else:
        print("\n❌ Cleanup failed!")


def run_tests():
    """Run migration tests"""
    print("Running migration tests...")
    print("=" * 50)
    
    try:
        # Import and run tests
        from migration.test_migration import run_integration_test
        import unittest
        import sys
        
        # Run unit tests
        loader = unittest.TestLoader()
        suite = loader.discover('migration', pattern='test_*.py')
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Run integration test
        print("\n" + "=" * 50)
        run_integration_test()
        
        if result.wasSuccessful():
            print("\n✅ All tests passed!")
        else:
            print(f"\n❌ {len(result.failures)} test(s) failed")
            sys.exit(1)
            
    except ImportError as e:
        print(f"Error importing test modules: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error running tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()