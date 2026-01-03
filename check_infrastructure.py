#!/usr/bin/env python3
"""
Quick test script to verify the SaaS infrastructure is set up correctly.
Run this before starting docker-compose to catch configuration issues.
"""

import sys
import os

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description}: {filepath} (MISSING)")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists"""
    if os.path.isdir(dirpath):
        print(f"✓ {description}: {dirpath}")
        return True
    else:
        print(f"✗ {description}: {dirpath} (MISSING)")
        return False

def main():
    print("Checking SaaS infrastructure setup...\n")
    
    all_good = True
    
    # Check docker-compose
    all_good &= check_file_exists("docker-compose.yml", "Docker Compose configuration")
    
    # Check API structure
    all_good &= check_directory_exists("saas/api", "API directory")
    all_good &= check_file_exists("saas/api/main.py", "API main module")
    all_good &= check_file_exists("saas/api/database.py", "Database configuration")
    all_good &= check_file_exists("saas/api/models.py", "Database models")
    all_good &= check_directory_exists("saas/api/routers", "API routers")
    
    # Check worker structure
    all_good &= check_directory_exists("saas/worker", "Worker directory")
    all_good &= check_file_exists("saas/worker/main.py", "Worker main module")
    all_good &= check_file_exists("saas/worker/conversion_engine.py", "Conversion engine")
    all_good &= check_file_exists("saas/worker/steps.py", "Pipeline steps")
    
    # Check migrations
    all_good &= check_file_exists("alembic.ini", "Alembic configuration")
    all_good &= check_directory_exists("saas/api/migrations", "Migrations directory")
    all_good &= check_directory_exists("saas/api/migrations/versions", "Migrations versions")
    
    # Check frontend
    all_good &= check_directory_exists("saas/web", "Web directory")
    all_good &= check_file_exists("saas/web/package.json", "Web package.json")
    all_good &= check_file_exists("saas/web/Dockerfile", "Web Dockerfile")
    
    # Check Dockerfiles
    all_good &= check_file_exists("Dockerfile.api", "API Dockerfile")
    
    # Check environment example
    all_good &= check_file_exists(".env.example", "Environment example")
    
    print("\n" + "="*60)
    if all_good:
        print("✓ All infrastructure files are present!")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and configure your values")
        print("2. Run: docker-compose up -d")
        print("3. Run migrations: docker-compose exec api alembic upgrade head")
        print("4. Check health: curl http://localhost:8000/api/v1/health")
        return 0
    else:
        print("✗ Some infrastructure files are missing!")
        print("Please review the output above and create missing files.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
