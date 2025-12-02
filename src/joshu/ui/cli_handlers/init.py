"""Initialization helpers for CLI."""

import logging
import os

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
    current_model = config_manager.get("model", "llama-3-8b")

    context_provider = ContextProvider()
    system_info = get_detailed_system_info()
    context_provider.set_system_info(system_info)

    # Ensure cloud usage is enabled if a cloud model is configured
    configured_model = os.getenv("OPENROUTER_MODEL") or "llama-3-8b"
    cloud_models = ["deepseek", "tongyi", "qwen", "kimi", "agentica", "glm"]

    if any(model in configured_model.lower() for model in cloud_models):
        if not os.getenv("JOSHU_USE_CLOUD"):
            os.environ["JOSHU_USE_CLOUD"] = "true"

    # Establish connection
    try:
        from joshu.core.translate import establish_connection

        if establish_connection(current_model):
            logger.debug("Connection established successfully")
        else:
            logger.debug("Failed to establish connection, will retry on first request")
    except Exception as e:
        logger.debug(f"Connection establishment skipped: {e}")

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
    logging.getLogger("joshu.core.translate").setLevel(logging.INFO)
