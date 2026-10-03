"""Initialization helpers for CLI."""

import logging

from dotenv import load_dotenv

from joshu.core.config import get_config_manager
from joshu.core.context_provider import ContextProvider
from joshu.tools.system_info import get_detailed_system_info

logger = logging.getLogger(__name__)


def initialize_context() -> tuple:
    """
    Initialize context provider and configuration.

    Returns:
        tuple: (config_manager, context_provider, current_model)
    """
    load_dotenv()

    config_manager = get_config_manager()
    current_model = config_manager.get("model")

    context_provider = ContextProvider()
    system_info = get_detailed_system_info()
    context_provider.set_system_info(system_info)

    return config_manager, context_provider, current_model


def setup_logging(verbose: bool = False) -> None:
    """Setup logging based on verbose mode."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("joshu").setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("joshu").setLevel(logging.WARNING)
        logger.setLevel(logging.WARNING)

    # Reduce logging from specific modules
    logging.getLogger("httpx").setLevel(logging.WARNING)
