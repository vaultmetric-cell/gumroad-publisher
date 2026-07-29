"""
api_client.py — Gumroad API v2 client.

Handles:
  - Authentication (Bearer token via Authorization header)
  - Product creation OR update (idempotent by slug lookup)
  - File upload (multipart/form-data)
  - Pricing, description, tags, and publish state
  - Retry logic with exponential back-off

Gumroad API base: https://api.gumroad.com/v2
Docs: https://app.gumroad.com/api
"""

import time
import json
from pathlib import Path
from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ProductConfig


BASE_URL = "https://api.gumroad.com/v2"


# ──────────────────────────────────────────────
#  Session with retries
# ──────────────────────────────────────────────

def _build_session(api_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_token}",
    })
    retry = Retry(
        total=4,
        backoff_factor=1.5,           # waits: 0s, 1.5s, 3s, 6s
        status_forcelist={429, 500, 502, 503, 504},
        allowed_methods={"GET", "POST", "PUT", "DELETE", "PATCH"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


# ──────────────────────────────────────────────
#  Gumroad API client
# ──────────────────────────────────────────────

class GumroadClient:
    def __init__(self, api_token: str, logger):
        self.api_token = api_token
        self.logger    = logger
        self.session   = _build_session(api_token)

    # ── internal request helper ──

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        self.logger.debug(f"API {method.upper()} {url}")
        resp = self.session.request(method, url, timeout=120, **kwargs)

        try:
            body = resp.json()
        except Exception:
            body = {"success": False, "message": resp.text}

        if not resp.ok or not body.get("success", False):
            msg = body.get("message", f"HTTP {resp.status_code}")
            raise GumroadAPIError(f"{method.upper()} {endpoint} failed: {msg}", resp.status_code, body)

        return body

    # ── product operations ──

    def list_products(self) -> list:
        """Return all products for the authenticated account."""
        body = self._request("GET", "products")
        return body.get("products", [])

    def find_product_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Look for an existing product whose custom_permalink matches slug.
        Returns the product dict or None.
        """
        products = self.list_products()
        for p in products:
            if p.get("custom_permalink") == slug or p.get("url", "").rstrip("/").endswith(slug):
                return p
        return None

    def create_product(self, product: ProductConfig, version: str) -> Dict:
        """Create a brand-new product on Gumroad."""
        data = self._product_payload(product, version)
        self.logger.info(f"Creating new Gumroad product: {product.name!r}")
        body = self._request("POST", "products", data=data)
        prod = body["product"]
        self.logger.info(f"Product created — ID: {prod['id']}")
        return prod

    def update_product(self, product_id: str, product: ProductConfig, version: str) -> Dict:
        """Update an existing product's metadata."""
        data = self._product_payload(product, version)
        self.logger.info(f"Updating product {product_id} → version {version}")
        body = self._request("PUT", f"products/{product_id}", data=data)
        return body["product"]

    def get_or_create_product(self, product: ProductConfig, version: str) -> tuple:
        """
        Returns (product_dict, is_new: bool).
        Looks up by slug first; creates if not found.
        """
        existing = self.find_product_by_slug(product.slug)
        if existing:
            self.logger.info(f"Found existing product: {existing['id']} ({existing.get('name')})")
            updated = self.update_product(existing["id"], product, version)
            return updated, False
        else:
            created = self.create_product(product, version)
            return created, True

    # ── file upload ──

    def upload_file(self, product_id: str, zip_path: Path, version: str) -> Dict:
        """
        Upload the product ZIP as a new product file.
        Gumroad supports multiple files per product; old files are NOT auto-deleted.
        We delete previous files for this product first to keep things clean.
        """
        self._delete_existing_files(product_id)

        file_name = f"{zip_path.stem}-v{version}.zip" if not zip_path.stem.endswith(f"-v{version}") else zip_path.name
        file_size = zip_path.stat().st_size
        self.logger.info(f"Uploading {zip_path.name} ({_human_size(file_size)}) …")

        with open(zip_path, "rb") as fh:
            body = self._request(
                "POST",
                f"products/{product_id}/product_files",
                files={"file": (file_name, fh, "application/zip")},
            )

        product_file = body.get("product_file", body)
        self.logger.info(f"Upload complete — file ID: {product_file.get('id', 'unknown')}")
        return product_file

    def _delete_existing_files(self, product_id: str) -> None:
        """Remove all current files attached to the product before uploading new version."""
        try:
            body = self._request("GET", f"products/{product_id}/product_files")
            files = body.get("product_files", [])
        except GumroadAPIError:
            return   # if endpoint unavailable, skip cleanup gracefully

        for f in files:
            fid = f.get("id")
            if fid:
                try:
                    self._request("DELETE", f"products/{product_id}/product_files/{fid}")
                    self.logger.debug(f"Deleted old file: {fid}")
                except GumroadAPIError as e:
                    self.logger.warning(f"Could not delete file {fid}: {e}")

    # ── publish / unpublish ──

    def set_published(self, product_id: str, published: bool) -> None:
        action = "enable" if published else "disable"
        endpoint = f"products/{product_id}/{action}"
        self._request("PUT", endpoint)
        state = "PUBLISHED" if published else "UNPUBLISHED"
        self.logger.info(f"Product {product_id} → {state}")

    # ── payload builder ──

    def _product_payload(self, product: ProductConfig, version: str) -> Dict:
        """Build the form-data dict for create/update calls."""
        desc_with_version = (
            f"{product.description}\n\n**Version:** {version}"
            if product.description
            else f"Version: {version}"
        )
        payload = {
            "name":                 product.name,
            "description":          desc_with_version,
            "price":                str(product.price_cents),
            "currency":             product.currency,
            "custom_permalink":     product.slug,
            "published":            "true" if product.published else "false",
        }
        if product.suggested_price_cents > 0:
            payload["suggested_price"] = str(product.suggested_price_cents)
        if product.custom_summary:
            payload["custom_summary"] = product.custom_summary
        if product.tags:
            payload["tags"] = json.dumps(product.tags)
        return payload


# ──────────────────────────────────────────────
#  Custom exception
# ──────────────────────────────────────────────

class GumroadAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.body        = body or {}


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
