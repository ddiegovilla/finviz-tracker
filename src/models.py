from dataclasses import dataclass


@dataclass(frozen=True)
class FilterDefinition:
    name: str
    url: str


@dataclass(frozen=True)
class Stock:
    ticker: str
    company: str
    sector: str
    industry: str


@dataclass(frozen=True)
class ScreenerPage:
    stocks: list[Stock]
    row_numbers: list[int]
    total: int


@dataclass(frozen=True)
class RankedStock:
    ticker: str
    company: str
    sector: str
    industry: str
    match_count: int
    matched_filters: list[str]
