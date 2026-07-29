"""config.py - Configuration loader and validator."""
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

try:
    import yaml as _yaml
    def _parse_config(text):
        return _yaml.safe_load(text)
except ImportError:
    def _parse_config(text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise ImportError("PyYAML not installed and config is not valid JSON.")

@dataclass
class ProductConfig:
    name: str
    slug: str
    description: str
    price_cents: int
    suggested_price_cents: int = 0
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    currency: str = "usd"
    is_physical: bool = False
    require_shipping: bool = False
    published: bool = True
    custom_summary: str = ""

@dataclass
class BuildConfig:
    source_dir: str
    output_dir: str = "builds"
    include_patterns: List[str] = field(default_factory=lambda: ["**/*"])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "**/__pycache__/**", "**/.DS_Store", "**/Thumbs.db",
        "**/*.pyc", "**/.git/**"
    ])
    readme_template: str = "templates/README.md.j2"
    changelog_template: str = "templates/CHANGELOG.md.j2"

@dataclass
class GumroadConfig:
    api_token: str
    product: ProductConfig
    build: BuildConfig
    log_file: str = "logs/publish.log"
    version_file: str = ".version"

def load_config(path: str = "gumroad_config.yaml") -> GumroadConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        print(f"[ERROR] Config file not found: {cfg_path.resolve()}")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = _parse_config(f.read())
    api_token = os.environ.get("GUMROAD_API_TOKEN") or raw.get("api_token", "")
    if not api_token:
        print("[ERROR] GUMROAD_API_TOKEN not set.")
        sys.exit(1)
    p = raw.get("product", {})
    product = ProductConfig(
        name=p["name"],
        slug=p.get("slug", _slugify(p["name"])),
        description=p.get("description", ""),
        price_cents=int(p.get("price_cents", 0)),
        suggested_price_cents=int(p.get("suggested_price_cents", 0)),
        tags=p.get("tags", []),
        categories=p.get("categories", []),
        currency=p.get("currency", "usd"),
        is_physical=p.get("is_physical", False),
        require_shipping=p.get("require_shipping", False),
        published=p.get("published", True),
        custom_summary=p.get("custom_summary", ""),
    )
    b = raw.get("build", {})
    build = BuildConfig(
        source_dir=b["source_dir"],
        output_dir=b.get("output_dir", "builds"),
        include_patterns=b.get("include_patterns", ["**/*"]),
        exclude_patterns=b.get("exclude_patterns", [
            "**/__pycache__/**", "**/.DS_Store", "**/Thumbs.db",
            "**/*.pyc", "**/.git/**"
        ]),
        readme_template=b.get("readme_template", "templates/README.md.j2"),
        changelog_template=b.get("changelog_template", "templates/CHANGELOG.md.j2"),
    )
    return GumroadConfig(
        api_token=api_token, product=product, build=build,
        log_file=raw.get("log_file", "logs/publish.log"),
        version_file=raw.get("version_file", ".version"),
    )

def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")
