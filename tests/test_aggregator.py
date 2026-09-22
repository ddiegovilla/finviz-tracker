from src.aggregator import aggregate
from src.models import Stock


def test_deduplicates_per_filter_and_sorts_with_exact_names():
    first = Stock("TESTA", "Test A", "Sector", "Industry")
    second = Stock("TESTB", "Test B", "Sector", "Industry")
    third = Stock("TESTC", "Test C", "Sector", "Industry")
    result = aggregate({"Momentum": [second, first, first, third], "Volumen climático": [second]})
    assert [stock.ticker for stock in result] == ["TESTB", "TESTA", "TESTC"]
    assert result[0].match_count == 2
    assert result[0].matched_filters == ["Momentum", "Volumen climático"]
    assert result[1].match_count == 1
    assert aggregate({"Momentum": []}) == []
