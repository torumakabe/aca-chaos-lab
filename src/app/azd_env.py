"""Azure Developer CLI environment integration."""

import os
import shutil
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
    # First check if azd is available
    azd_path = shutil.which("azd")
    if not azd_path:
        return os.getenv(key, default)
    
    # Try to get from azd
    try:
        result = subprocess.run(  # noqa: S603
            [azd_path, "env", "get-value", key],
            capture_output=True,
            text=True,
            check=False,
            timeout=10  # Add timeout for safety
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
        # azd not available or error occurred
        pass
    
    # Fall back to OS environment
    return os.getenv(key, default)


def is_azd_available() -> bool:
    """Check if azd CLI is available."""
    azd_path = shutil.which("azd")
    if not azd_path:
        return False
        
    try:
        result = subprocess.run(  # noqa: S603
            [azd_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5  # Add timeout for safety
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False