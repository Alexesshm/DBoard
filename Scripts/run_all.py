"""
DBoard - Main Runner Script
Runs all scripts to update dashboard data.
"""

import subprocess
import sys
import os
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

def run_script(script_name):
    """Run a Python script and return success status."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    print(f"\n{'='*50}")
    print(f">> Running: {script_name}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Warnings:\n{result.stderr}")
            
        if result.returncode == 0:
            print(f"[OK] {script_name} - success!")
            return True
        else:
            print(f"[FAIL] {script_name} - error (code: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error running {script_name}: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("DBOARD - Dashboard Data Update")
    print(f"Time: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("="*60)
    
    scripts = [
        'fetch_wb_data.py',
        'fetch_ozon_data.py', 
        'prepare_dashboard_data.py'
    ]
    
    results = {}
    for script in scripts:
        results[script] = run_script(script)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY:")
    print("="*60)
    
    success_count = sum(results.values())
    total_count = len(results)
    
    for script, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {script}")
    
    print(f"\n  Success: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\nAll data updated! Open index.html in browser.")
    else:
        print("\nSome scripts failed. Check errors above.")
    
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
