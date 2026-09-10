"""Simple keyword-based editorial tag extraction (Phase 17.1)."""

from __future__ import annotations

import re

# Normalized display tags keyed by lowercase match token.
COMPANY_TAGS: dict[str, str] = {
    "apple": "Apple",
    "google": "Google",
    "alphabet": "Alphabet",
    "microsoft": "Microsoft",
    "amazon": "Amazon",
    "meta": "Meta",
    "facebook": "Meta",
    "nvidia": "NVIDIA",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "deepmind": "DeepMind",
    "tesla": "Tesla",
    "boeing": "Boeing",
    "lockheed": "Lockheed",
    "raytheon": "Raytheon",
    "northrop": "Northrop",
    "pfizer": "Pfizer",
    "moderna": "Moderna",
    "intel": "Intel",
    "amd": "AMD",
    "tsmc": "TSMC",
    "samsung": "Samsung",
    "huawei": "Huawei",
    "bytedance": "ByteDance",
    "tiktok": "TikTok",
}

COUNTRY_TAGS: dict[str, str] = {
    "united states": "United States",
    "u.s.": "United States",
    "usa": "United States",
    "china": "China",
    "russia": "Russia",
    "ukraine": "Ukraine",
    "taiwan": "Taiwan",
    "israel": "Israel",
    "iran": "Iran",
    "saudi arabia": "Saudi Arabia",
    "india": "India",
    "european union": "European Union",
    "eu ": "European Union",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "germany": "Germany",
    "france": "France",
    "japan": "Japan",
    "south korea": "South Korea",
}

TECHNOLOGY_TAGS: dict[str, str] = {
    "artificial intelligence": "AI",
    " ai ": "AI",
    "machine learning": "Machine Learning",
    "llm": "LLM",
    "large language model": "LLM",
    "semiconductor": "Semiconductor",
    "chip": "Chips",
    "hbm": "HBM",
    "memory": "Memory",
    "cloud computing": "Cloud",
    "cybersecurity": "Cybersecurity",
    "ransomware": "Ransomware",
    "quantum": "Quantum",
    "5g": "5G",
    "ev ": "EV",
    "electric vehicle": "EV",
    "solar": "Solar",
    "wind energy": "Wind Energy",
    "nuclear": "Nuclear",
}

PRODUCT_TAGS: dict[str, str] = {
    "iphone": "iPhone",
    "chatgpt": "ChatGPT",
    "gpt-4": "GPT-4",
    "gpt-5": "GPT-5",
    "windows": "Windows",
    "android": "Android",
    "f-35": "F-35",
    "starlink": "Starlink",
}

REGULATION_TAGS: dict[str, str] = {
    "fda": "FDA",
    "sec": "SEC",
    "ftc": "FTC",
    "cisa": "CISA",
    "gdpr": "GDPR",
    "antitrust": "Antitrust",
    "export controls": "Export Controls",
    "ndaa": "NDAA",
    "inflation reduction act": "Inflation Reduction Act",
}

_TAG_SOURCES: tuple[tuple[dict[str, str], str], ...] = (
    (COMPANY_TAGS, "company"),
    (COUNTRY_TAGS, "country"),
    (TECHNOLOGY_TAGS, "technology"),
    (PRODUCT_TAGS, "product"),
    (REGULATION_TAGS, "regulation"),
)

# Acronyms in ALL CAPS in titles — e.g. "HBM", "AI", "FDA"
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}\b")


def extract_editorial_tags(title: str, summary: str) -> list[str]:
    """
    Extract normalized editorial tags from title and summary.
    Returns deduplicated tags in discovery order (title matches first).
    """
    text = (title + " " + (summary or "")).lower()
    padded = f" {text} "
    seen: set[str] = set()
    tags: list[str] = []

    for source_map, _category in _TAG_SOURCES:
        for token, display in source_map.items():
            if token in text or token in padded:
                if display not in seen:
                    seen.add(display)
                    tags.append(display)

    for match in _ACRONYM_RE.findall(title):
        if match not in seen and len(match) >= 2:
            seen.add(match)
            tags.append(match)

    return tags[:12]
