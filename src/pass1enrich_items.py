from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INPUT_PATH = DATA_DIR / "rss_items.json"
OUTPUT_PATH = DATA_DIR / "pass1enriched_items.json"


def load_json_file(path: Path) -> list[dict[str, Any]]:
    """Load a JSON file that contains a top-level list of objects."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected top-level list in {path}, got {type(data).__name__}")

    return data


def save_json_file(path: Path, data: list[dict[str, Any]]) -> None:
    """Save JSON with readable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(value: str) -> str:
    """Create a simple slug for IDs."""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"^-+|-+$", "", value)
    return value


def stable_article_id(source: str, link: str, title: str) -> str:
    """
    Build a stable deterministic ID.

    Primary key logic:
    - use source + link when link exists
    - otherwise use source + title
    """
    identity_value = link.strip() if link.strip() else title.strip()
    raw_key = f"{source.strip()}|{identity_value}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    source_slug = slugify(source) or "source"
    return f"{source_slug}_{digest}"


def parse_published_at(published: str) -> str | None:
    """Convert RSS pubDate string into ISO 8601."""
    if not published or not isinstance(published, str):
        return None

    try:
        dt = parsedate_to_datetime(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def clean_text(text: str) -> str:
    """
    Light cleanup only.

    We are not trying to summarize, rewrite, or heavily normalize content here.
    """
    if not text or not isinstance(text, str):
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def word_count(text: str) -> int:
    """Count words in a simple, transparent way."""
    if not text:
        return 0

    return len(re.findall(r"\b\w+\b", text))


def build_empty_ai_fields() -> dict[str, Any]:
    """
    Pass 1 placeholders.

    These fields stay blank until pass 2 AI enrichment fills them in.
    """
    return {
        "ai_summary_short": "",
        "ai_summary_bullets": [],
        "primary_topic": "",
        "secondary_topics": [],
        "tags": [],
        "strategic_implications": [],
        "investment_implications": {
            "potential_winners": [],
            "potential_losers": [],
            "mentioned_tickers": [],
            "implied_tickers": [],
            "implied_sectors": [],
            "signal_strength": 0,
        },
    }


def determine_pass1_status(raw_item: dict[str, Any], cleaned_text_value: str) -> tuple[str, str | None]:
    """Set pass 1 status based on raw fetch success and usable text."""
    fetch_success = bool(raw_item.get("article_fetch_success", False))
    fetch_error = raw_item.get("article_fetch_error")

    if fetch_success and cleaned_text_value:
        return "ready_for_ai", None

    if not fetch_success:
        return "skipped", str(fetch_error or "article_fetch_success was false")

    return "skipped", "Missing article_text"


def enrich_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Transform one raw RSS item into the pass 1 enriched schema."""
    source = str(raw_item.get("source", "") or "").strip()
    title = str(raw_item.get("title", "") or "").strip()
    link = str(raw_item.get("link", "") or "").strip()
    published = str(raw_item.get("published", "") or "").strip()
    raw_text = str(raw_item.get("article_text", "") or "")

    article_id = stable_article_id(source=source, link=link, title=title)
    published_at = parse_published_at(published)
    cleaned = clean_text(raw_text)
    cleaned_wc = word_count(cleaned)
    enrichment_status, enrichment_error = determine_pass1_status(raw_item, cleaned)

    enriched_item: dict[str, Any] = {
        "id": article_id,
        "source": source,
        "title": title,
        "link": link,
        "published_at": published_at,
        "enrichment_status": enrichment_status,
        "enrichment_error": enrichment_error,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "cleaned_text": cleaned,
        "cleaned_word_count": cleaned_wc,
    }

    enriched_item.update(build_empty_ai_fields())
    return enriched_item


def enrich_all_items(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run pass 1 enrichment across all raw items."""
    return [enrich_item(item) for item in raw_items]


def print_summary(enriched_items: list[dict[str, Any]]) -> None:
    total = len(enriched_items)
    ready_for_ai = sum(1 for item in enriched_items if item["enrichment_status"] == "ready_for_ai")
    skipped = sum(1 for item in enriched_items if item["enrichment_status"] == "skipped")

    print(f"Total items processed: {total}")
    print(f"Ready for AI enrichment: {ready_for_ai}")
    print(f"Skipped: {skipped}")
    print(f"Saved pass1 enriched items to: {OUTPUT_PATH}")


def main() -> None:
    raw_items = load_json_file(INPUT_PATH)
    enriched_items = enrich_all_items(raw_items)
    save_json_file(OUTPUT_PATH, enriched_items)
    print_summary(enriched_items)


if __name__ == "__main__":
    main()