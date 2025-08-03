"""Helper module to get environment values from azd or environment variables."""

import os
import subprocess


def get_env_value(key: str, default: str | None = None) -> str | None:
    """Get value from azd env or fallback to environment variable.

    Args:
        key: The environment variable key
        default: Default value if not found

    Returns:
        The value from azd or environment variable, or default
    """
    # Try to get from azd first
    try:
        result = subprocess.run(
            ["azd", "env", "get-value", key],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        # azd not available
        pass

    # Fallback to environment variable
    return os.getenv(key, default)


def is_azd_available() -> bool:
    """Check if azd CLI is available."""
    try:
        subprocess.run(["azd", "--version"], capture_output=True, check=False)
        return True
    except FileNotFoundError:
        return False


def load_azd_environment() -> dict:
    """Load all common azd environment values.

    Returns:
        Dictionary of environment values
    """
    env = {}

    if is_azd_available():
        print("Using Azure Developer CLI environment values...")
    else:
        print("Azure Developer CLI not found, using environment variables...")

    # Load common values
    env["RESOURCE_GROUP"] = get_env_value(
        "AZURE_RESOURCE_GROUP", os.getenv("RESOURCE_GROUP")
    )
    env["CONTAINER_APP_NAME"] = get_env_value(
        "SERVICE_APP_NAME", os.getenv("CONTAINER_APP_NAME")
    )
    env["CONTAINER_APP_URI"] = get_env_value(
        "SERVICE_APP_URI", os.getenv("CONTAINER_APP_URI")
    )
    env["REDIS_HOST"] = get_env_value("AZURE_REDIS_HOST", os.getenv("REDIS_HOST"))
    env["LOCATION"] = get_env_value("AZURE_LOCATION", os.getenv("LOCATION"))

    # For network operations, try to get NSG name
    if not os.getenv("NSG_NAME") and env["RESOURCE_GROUP"]:
        try:
            result = subprocess.run(
                [
                    "az",
                    "network",
                    "nsg",
                    "list",
                    "-g",
                    env["RESOURCE_GROUP"],
                    "--query",
                    "[0].name",
                    "-o",
                    "tsv",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                env["NSG_NAME"] = result.stdout.strip()
        except:
            pass
    else:
        env["NSG_NAME"] = os.getenv("NSG_NAME")

    return env
