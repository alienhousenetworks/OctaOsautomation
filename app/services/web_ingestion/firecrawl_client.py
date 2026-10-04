"""Firecrawl Web Scraping & Crawling Client.

Provides enterprise-grade web page scraping and multi-page site crawling with:
1. SSRF guards (rejects loopback, link-local, and RFC 1918 private IP ranges)
2. Per-tenant BYOK credentials with server env fallback
3. Support for Firecrawl Cloud and self-hosted instances via FIRECRAWL_API_URL
4. Structured markdown normalization and robust retries
"""
import os
import socket
import logging
import ipaddress
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


def validate_target_url(url: str) -> str:
    """Validate URL and enforce SSRF protections against internal network scanning."""
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    cleaned_url = url.strip()
    parsed_initial = urlparse(cleaned_url)
    if parsed_initial.scheme and parsed_initial.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme: '{parsed_initial.scheme}'. Only HTTP and HTTPS are permitted.")

    if not cleaned_url.startswith(("http://", "https://")):
        cleaned_url = f"https://{cleaned_url}"

    parsed = urlparse(cleaned_url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Invalid URL: could not extract hostname from '{url}'")

    # Reject localhost, local domains, and AWS/cloud metadata services
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "metadata.google.internal", "169.254.169.254"):
        raise ValueError("Crawling internal loopback or cloud metadata services is prohibited.")

    # Resolve IP address to detect DNS rebinding or private subnet targets
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"URL resolves to disallowed private network IP: {ip_str}")
    except (socket.gaierror, UnicodeError) as e:
        # If hostname resolution fails here, let the crawl client attempt it or raise informative error
        logger.debug(f"Host resolution check for {hostname}: {e}")

    return cleaned_url


class FirecrawlClient:
    def __init__(self, db: Optional[Session] = None, tenant_id: Optional[str] = None, api_key: Optional[str] = None):
        self.db = db
        self.tenant_id = tenant_id
        self.api_key = api_key or self._resolve_api_key()
        self.api_url = os.getenv("FIRECRAWL_API_URL", "").strip() or None

        if not self.api_key and not self.api_url:
            raise ValueError(
                "No Firecrawl API key configured. "
                "Please configure Firecrawl under Platform Setup → API Settings or set FIRECRAWL_API_KEY."
            )

    def _resolve_api_key(self) -> str:
        """Resolve API key using BYOK from tenant settings, falling back to server env."""
        if self.db and self.tenant_id:
            try:
                from app.services.ai_gateway import ai_gateway
                key = ai_gateway._get_api_key(self.db, self.tenant_id, "firecrawl")
                if key:
                    return key
            except Exception as e:
                logger.warning(f"Could not fetch tenant Firecrawl key: {e}")

        return os.getenv("FIRECRAWL_API_KEY", "").strip()

    def _get_app(self):
        """Instantiate Firecrawl SDK app."""
        from firecrawl import FirecrawlApp
        kwargs = {"api_key": self.api_key or "self-hosted"}
        if self.api_url:
            kwargs["api_url"] = self.api_url
        return FirecrawlApp(**kwargs)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def scrape_url(self, url: str) -> Dict[str, Any]:
        """Scrape a single web page and return clean markdown and metadata."""
        safe_url = validate_target_url(url)
        app = self._get_app()

        try:
            doc = app.scrape(safe_url, formats=["markdown"])
            # In firecrawl v2, doc can be a Document model or dict
            markdown = getattr(doc, "markdown", None)
            if markdown is None and isinstance(doc, dict):
                markdown = doc.get("markdown", "")
            
            metadata = getattr(doc, "metadata", None) or {}
            if hasattr(metadata, "model_dump"):
                metadata = metadata.model_dump()
            elif not isinstance(metadata, dict):
                metadata = {}

            title = metadata.get("title") or metadata.get("ogTitle") or safe_url

            return {
                "url": safe_url,
                "markdown": markdown or "",
                "title": title,
                "metadata": metadata,
            }
        except Exception as e:
            logger.error(f"Firecrawl scrape failed for {safe_url}: {e}")
            raise

    def crawl_website(
        self,
        url: str,
        max_pages: int = 50,
        crawl_depth: int = 2,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl a website up to max_pages and depth, returning all crawled markdown pages."""
        safe_url = validate_target_url(url)
        app = self._get_app()

        # Enforce reasonable guardrails: 1 to 100 pages
        capped_limit = max(1, min(max_pages, 100))
        capped_depth = max(1, min(crawl_depth, 5))

        crawl_kwargs: Dict[str, Any] = {
            "limit": capped_limit,
            "max_discovery_depth": capped_depth,
            "scrape_options": {"formats": ["markdown"]},
        }
        if include_paths:
            crawl_kwargs["include_paths"] = include_paths
        if exclude_paths:
            crawl_kwargs["exclude_paths"] = exclude_paths

        logger.info(f"Starting Firecrawl crawl for {safe_url} (limit={capped_limit}, depth={capped_depth})")

        try:
            job = app.crawl(safe_url, **crawl_kwargs)
            # job is a CrawlJob instance with .data list of documents
            raw_docs = getattr(job, "data", []) or []
            if not raw_docs and isinstance(job, dict):
                raw_docs = job.get("data", [])

            results = []
            for doc in raw_docs:
                markdown = getattr(doc, "markdown", None)
                if markdown is None and isinstance(doc, dict):
                    markdown = doc.get("markdown", "")

                metadata = getattr(doc, "metadata", None) or {}
                if hasattr(metadata, "model_dump"):
                    metadata = metadata.model_dump()
                elif not isinstance(metadata, dict):
                    metadata = {}

                doc_url = metadata.get("sourceURL") or metadata.get("url") or safe_url
                doc_title = metadata.get("title") or metadata.get("ogTitle") or doc_url

                if markdown and markdown.strip():
                    results.append({
                        "url": doc_url,
                        "title": doc_title,
                        "markdown": markdown.strip(),
                        "metadata": metadata,
                    })

            logger.info(f"Firecrawl completed crawl for {safe_url}: {len(results)} pages extracted.")
            return results
        except Exception as e:
            logger.error(f"Firecrawl crawl failed for {safe_url}: {e}")
            raise
