import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .models import FilterDefinition
from .app_paths import resource_root


ROOT = resource_root()


def load_filters(path: Path = ROOT / "config" / "filters.json") -> list[FilterDefinition]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Filter configuration must be a nonempty list")
    filters = []
    names = set()
    for entry in entries:
        name, url = entry["name"], entry["url"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Filter names must be nonempty and unique")
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "finviz.com"
            or parsed.path not in ("/screener", "/screener.ashx")
            or query.get("v") != ["111"]
            or not query.get("f")
        ):
            raise ValueError(f"Invalid Finviz overview URL for {name}")
        names.add(name)
        filters.append(FilterDefinition(name, url))
    return filters
