"""
Pytest configuration to add project root to Python path
"""
import sys
from pathlib import Path

# Add project root to Python path (parent of 'project' directory)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
