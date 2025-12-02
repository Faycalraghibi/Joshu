"""
System information tool for Joshu Assistant.
Provides consistent and reliable system detection with error handling.
"""

import logging
import platform

logger = logging.getLogger(__name__)


def get_system_info() -> str:
    """
    Get information about the current system for command generation.

    Returns:
        str: System information string (e.g., "Windows", "macOS", "Linux")

    This function provides a consistent way to detect the operating system
    with proper error handling. It should be used throughout the application
    instead of calling platform.system() directly.
    """
    try:
        system = platform.system()
        if system == "Windows":
            return "Windows"
        elif system == "Darwin":
            return "macOS"
        elif system == "Linux":
            return "Linux"
        else:
            # Handle unknown systems gracefully
            logger.warning(f"Unknown system type detected: {system}")
            return f"Unix-like ({system})"
    except Exception as e:
        logger.error(f"Failed to detect system information: {e}")
        # Fallback to a generic Unix-like system
        return "Unix-like (unknown)"


def get_detailed_system_info() -> str:
    """
    Get detailed system information including version/release.

    Returns:
        str: Detailed system information string

    This function provides more detailed system information that can be
    used for context-aware command generation.
    """
    try:
        system = platform.system()
        release = platform.release()
        version = platform.version()

        if system == "Windows":
            return f"Windows {release}"
        elif system == "Darwin":
            return f"macOS {release}"
        elif system == "Linux":
            # Try to get distribution info if available
            try:
                import distro

                distro_info = distro.name(pretty=True)
                if distro_info:
                    return f"{distro_info} ({system} {release})"
            except ImportError:
                pass
            return f"{system} {release}"
        else:
            return f"{system} {release} ({version})"
    except Exception as e:
        logger.error(f"Failed to get detailed system information: {e}")
        # Fallback to basic system info
        return get_system_info()
