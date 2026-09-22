import logging
from collections.abc import Mapping, Sequence

from .models import RankedStock, Stock


LOGGER = logging.getLogger(__name__)


def aggregate(results: Mapping[str, Sequence[Stock]]) -> list[RankedStock]:
    metadata = {}
    matches = {}
    for filter_name, stocks in results.items():
        for stock in stocks:
            if stock.ticker in metadata and metadata[stock.ticker] != stock:
                LOGGER.warning("Metadata changed for %s between filters; using first observation", stock.ticker)
            metadata.setdefault(stock.ticker, stock)
            names = matches.setdefault(stock.ticker, [])
            if filter_name not in names:
                names.append(filter_name)
    ranked = [
        RankedStock(stock.ticker, stock.company, stock.sector, stock.industry, len(matches[ticker]), matches[ticker])
        for ticker, stock in metadata.items()
    ]
    return sorted(ranked, key=lambda stock: (-stock.match_count, stock.ticker))
