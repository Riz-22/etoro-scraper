import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import requests

from extractors.stock_parser import parse_stock_page
from extractors.investor_parser import parse_investor_page
from extractors.post_parser import parse_posts_page
from outputs.json_exporter import export_to_json
from outputs.csv_exporter import export_to_csv

FIELD_NAMES = [
    "stock_name",
    "ticker",
    "investor_name",
    "investor_stats",
    "post_content",
    "comment_text",
    "likes_count",
    "post_date",
    "category",
    "source_url",
]

def project_root() -> Path:
    """Return the root directory of the project."""
    return Path(__file__).resolve().parents[1]

def load_settings() -> Dict[str, Any]:
    """
    Load settings from src/config/settings.example.json.

    In a real-world project this would likely read from a non-example file
    or environment variables. For this demo we keep it simple.
    """
    root = project_root()
    settings_path = root / "src" / "config" / "settings.example.json"

    if not settings_path.exists():
        logging.warning("Settings file %s not found, using defaults.", settings_path)
        return {
            "input_file": str(root / "data" / "inputs.sample.json"),
            "output_json": str(root / "data" / "output.sample.json"),
            "output_csv": str(root / "data" / "output.sample.csv"),
            "http": {
                "timeout": 10,
                "user_agent": "EtoroScraper/1.0 (+https://bitbash.dev)",
            },
            "log_level": "INFO",
        }

    with settings_path.open("r", encoding="utf-8") as f:
        settings = json.load(f)

    # Ensure required keys exist with sensible defaults
    defaults = {
        "input_file": str(root / "data" / "inputs.sample.json"),
        "output_json": str(root / "data" / "output.sample.json"),
        "output_csv": str(root / "data" / "output.sample.csv"),
        "http": {
            "timeout": 10,
            "user_agent": "EtoroScraper/1.0 (+https://bitbash.dev)",
        },
        "log_level": "INFO",
    }

    def merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in extra.items():
            if isinstance(value, dict):
                node = base.setdefault(key, {})
                if isinstance(node, dict):
                    merge(node, value)
                else:
                    base[key] = value
            else:
                base.setdefault(key, value)
        return base

    return merge(settings, defaults)

def configure_logging(level: str) -> None:
    level_map = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }
    logging.basicConfig(
        level=level_map.get(level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

def load_input_urls(input_file: Path) -> List[Dict[str, Any]]:
    """Load input URLs and optional categories from JSON file."""
    if not input_file.exists():
        logging.error("Input file %s does not exist.", input_file)
        return []

    with input_file.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            logging.error("Failed to parse input file %s: %s", input_file, exc)
            return []

    if not isinstance(data, list):
        logging.error("Input file must contain a JSON array.")
        return []

    cleaned: List[Dict[str, Any]] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            logging.warning("Skipping non-object entry at index %s in inputs.", idx)
            continue
        url = entry.get("url")
        if not url:
            logging.warning("Skipping entry without URL at index %s.", idx)
            continue
        cleaned.append(
            {
                "url": url,
                "category": entry.get("category"),
                "notes": entry.get("notes"),
            }
        )
    return cleaned

def fetch_page(
    url: str, timeout: int, user_agent: str
) -> str:
    """Fetch raw HTML from a URL."""
    logging.info("Requesting %s", url)
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        )
        response.raise_for_status()
        logging.debug("Fetched %s bytes from %s", len(response.text), url)
        return response.text
    except requests.RequestException as exc:
        logging.error("Request failed for %s: %s", url, exc)
        return ""

def normalize_record(
    partial: Dict[str, Any],
    category: str | None,
    source_url: str,
) -> Dict[str, Any]:
    """
    Ensure a record has all required fields with sane defaults.

    partial may be produced by any extractor and can contain a subset.
    """
    record: Dict[str, Any] = {field: None for field in FIELD_NAMES}
    record.update(partial)

    # Guarantee presence of required contextual fields
    record["category"] = partial.get("category") or category or record["category"]
    record["source_url"] = partial.get("source_url") or source_url

    return record

def process_url(
    url: str,
    category: str | None,
    html: str,
) -> List[Dict[str, Any]]:
    """Run all extractors over a single HTML page."""
    if not html.strip():
        logging.warning("Empty HTML body for %s, skipping.", url)
        return []

    all_records: List[Dict[str, Any]] = []

    # Stock data
    try:
        stock_records = parse_stock_page(html, source_url=url, category=category)
        all_records.extend(
            normalize_record(rec, category, url) for rec in stock_records
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("Error in stock parser for %s: %s", url, exc)

    # Investor profiles
    try:
        investor_records = parse_investor_page(html, source_url=url, category=category)
        all_records.extend(
            normalize_record(rec, category, url) for rec in investor_records
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("Error in investor parser for %s: %s", url, exc)

    # Posts and comments
    try:
        post_records = parse_posts_page(html, source_url=url, category=category)
        all_records.extend(
            normalize_record(rec, category, url) for rec in post_records
        )
    except Exception as exc:  # noqa: BLE001
        logging.error("Error in posts parser for %s: %s", url, exc)

    if not all_records:
        logging.info("No records extracted from %s.", url)
    else:
        logging.info("Extracted %d records from %s.", len(all_records), url)

    return all_records

def main() -> None:
    settings = load_settings()
    configure_logging(settings.get("log_level", "INFO"))

    root = project_root()
    input_file = Path(settings["input_file"])
    if not input_file.is_absolute():
        input_file = root / input_file

    output_json = Path(settings["output_json"])
    if not output_json.is_absolute():
        output_json = root / output_json

    output_csv = Path(settings["output_csv"])
    if not output_csv.is_absolute():
        output_csv = root / output_csv

    http_settings = settings.get("http", {})
    timeout = int(http_settings.get("timeout", 10))
    user_agent = str(
        http_settings.get("user_agent", "EtoroScraper/1.0 (+https://bitbash.dev)")
    )

    urls = load_input_urls(input_file)
    if not urls:
        logging.error("No input URLs to process. Exiting.")
        return

    all_records: List[Dict[str, Any]] = []

    for entry in urls:
        url = entry["url"]
        category = entry.get("category")
        html = fetch_page(url, timeout=timeout, user_agent=user_agent)
        records = process_url(url=url, category=category, html=html)
        all_records.extend(records)

    if not all_records:
        logging.warning("No records extracted from any URL.")
        return

    # Persist results
    logging.info("Writing %d records to %s and %s", len(all_records), output_json, output_csv)
    export_to_json(all_records, output_json)
    export_to_csv(all_records, output_csv, fieldnames=FIELD_NAMES)

    logging.info("Done.")

if __name__ == "__main__":
    main()