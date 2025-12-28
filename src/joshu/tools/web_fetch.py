"""
Web fetch tools for Joshu Assistant.

Provides functionality for fetching and processing web page content from URLs.
This module enables the LLM to retrieve and summarize web content.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available. Install with: pip install httpx")

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None  # type: ignore
    BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not available. Install with: pip install beautifulsoup4")


DEFAULT_TIMEOUT = 15
DEFAULT_MAX_LENGTH = 50000
DEFAULT_USER_AGENT = "Joshu-Assistant/1.0 (Web Fetch Tool)"


def is_valid_url(url: str) -> bool:
    """
    Validate if a string is a valid HTTP/HTTPS URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid HTTP/HTTPS URL, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    try:
        result = urlparse(url.strip())
        # Only allow http and https schemes
        if result.scheme not in ("http", "https"):
            return False
        # Must have a netloc (domain)
        if not result.netloc:
            return False
        return True
    except Exception:
        return False


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    Fetch raw content from a URL using httpx.

    Args:
        url: URL to fetch content from
        timeout: Timeout in seconds for the request (default: 15)

    Returns:
        Dictionary containing:
            - success: bool indicating if fetch was successful
            - url: the original URL
            - content: the fetched content (converted to markdown if HTML)
            - content_type: the content type of the response
            - error: error message if success is False
    """
    if not HTTPX_AVAILABLE:
        return {
            "success": False,
            "url": url,
            "content": None,
            "content_type": None,
            "error": "httpx library not installed. Install with: pip install httpx",
        }

    if not is_valid_url(url):
        return {
            "success": False,
            "url": url,
            "content": None,
            "content_type": None,
            "error": f"Invalid URL: '{url}'. Only HTTP/HTTPS URLs are supported.",
        }

    try:
        logger.info(f"Fetching URL: {url}")

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        response = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)

        if response.status_code >= 400:
            return {
                "success": False,
                "url": url,
                "content": None,
                "content_type": response.headers.get("content-type"),
                "error": f"HTTP {response.status_code}: {response.text[:200] if response.text else 'No response body'}",
            }

        content_type = response.headers.get("content-type", "")

        # Convert HTML to markdown for better readability
        if "text/html" in content_type:
            content = html_to_markdown(response.text)
        else:
            content = response.text

        logger.info(f"Successfully fetched URL: {url} ({len(content)} chars)")

        return {
            "success": True,
            "url": url,
            "content": content,
            "content_type": content_type,
            "error": None,
        }

    except httpx.TimeoutException:
        error_msg = f"Request timed out after {timeout} seconds"
        logger.error(f"Timeout fetching {url}: {error_msg}")
        return {
            "success": False,
            "url": url,
            "content": None,
            "content_type": None,
            "error": error_msg,
        }

    except httpx.ConnectError as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"Connection error fetching {url}: {error_msg}")
        return {
            "success": False,
            "url": url,
            "content": None,
            "content_type": None,
            "error": error_msg,
        }

    except Exception as e:
        error_msg = f"Failed to fetch URL: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "url": url,
            "content": None,
            "content_type": None,
            "error": error_msg,
        }


def html_to_markdown(html: str) -> str:
    """
    Convert HTML content to readable markdown/text.

    Removes scripts, styles, and other non-content elements.
    Preserves structure like headings, paragraphs, lists, and links.

    Args:
        html: HTML content string

    Returns:
        Cleaned and formatted text/markdown string
    """
    if not html or not html.strip():
        return ""

    if not BS4_AVAILABLE:
        # Fallback: simple HTML tag removal
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    try:
        soup = BeautifulSoup(html, "html.parser")

        for element in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
            element.decompose()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if text and href:
                a.replace_with(f"[{text}]({href})")

        for i in range(1, 7):
            for h in soup.find_all(f"h{i}"):
                text = h.get_text(strip=True)
                h.replace_with(f"\n{'#' * i} {text}\n")

        for li in soup.find_all("li"):
            text = li.get_text(strip=True)
            li.replace_with(f"\n• {text}")

        text = soup.get_text(separator="\n")

        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]  # Remove empty lines
        text = "\n".join(lines)

        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    except Exception as e:
        logger.warning(f"HTML parsing failed, using fallback: {e}")
        # Fallback to simple regex
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def process_url_content(
    url: str,
    instruction: Optional[str] = None,
    max_length: int = DEFAULT_MAX_LENGTH,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Fetch URL and process content with optional instruction.

    This is the main entry point for the web fetch tool.
    It fetches content, applies truncation, and prepares the response
    for LLM consumption.

    Args:
        url: URL to fetch content from
        instruction: Optional processing instruction (e.g., "summarize", "extract main points")
        max_length: Maximum content length to return (default: 50000)
        timeout: Request timeout in seconds (default: 15)

    Returns:
        Dictionary containing:
            - success: bool indicating if processing was successful
            - url: the original URL
            - source: source attribution (same as URL)
            - content: the processed content
            - instruction: the processing instruction (if provided)
            - truncated: bool indicating if content was truncated
            - error: error message if success is False
    """
    fetch_result = fetch_url(url, timeout=timeout)

    if not fetch_result["success"]:
        return {
            "success": False,
            "url": url,
            "source": url,
            "content": None,
            "instruction": instruction,
            "truncated": False,
            "error": fetch_result["error"],
        }

    content = fetch_result["content"]
    truncated = False

    if content and len(content) > max_length:
        content = content[:max_length]
        truncated = True
        logger.info(f"Content truncated from {len(fetch_result['content'])} to {max_length} chars")

    return {
        "success": True,
        "url": url,
        "source": url,
        "content": content,
        "content_type": fetch_result.get("content_type"),
        "instruction": instruction,
        "truncated": truncated,
        "error": None,
    }


def format_fetch_result(fetch_response: Dict[str, Any]) -> str:
    """
    Format fetch results into a human-readable string.

    Args:
        fetch_response: Response dictionary from process_url_content()

    Returns:
        Formatted string representation of the fetched content
    """
    if not fetch_response.get("success"):
        return f"Failed to fetch URL: {fetch_response.get('error', 'Unknown error')}"

    output = [f"Content from: {fetch_response.get('source', fetch_response.get('url'))}\n"]

    if fetch_response.get("truncated"):
        output.append("[Content was truncated due to length]\n")

    if fetch_response.get("instruction"):
        output.append(f"Processing instruction: {fetch_response['instruction']}\n")

    output.append("---\n")
    output.append(fetch_response.get("content", "No content available"))

    return "\n".join(output)
