"""Azure Developer CLI environment integration."""

import os
import subprocess
from typing import Any


def get_azd_env_value(key: str, default: Any = None) -> Any:
    """Get environment value from azd if available, otherwise from OS environment.
    
    Args:
        key: Environment variable key
        default: Default value if not found
        
    Returns:
        The environment value or default
    """
    # First, try to get from azd
    try:
        result = subprocess.run(
            ["azd", "env", "get-value", key],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        # azd not available or error occurred
        pass
    
    # Fall back to OS environment
    return os.getenv(key, default)


def is_azd_available() -> bool:
    """Check if azd CLI is available."""
    try:
        result = subprocess.run(
            ["azd", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False