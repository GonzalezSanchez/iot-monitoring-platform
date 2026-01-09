"""
Pytest configuration for Smart Room Monitor
Configures Python path to allow imports without 'src.' prefix
"""
import sys
from pathlib import Path

# Add src directory to Python path so tests can import modules
# This matches the Lambda runtime structure where modules are in /var/task
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))
