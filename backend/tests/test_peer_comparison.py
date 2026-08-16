"""
Tests for the peer comparison agent.

The point of the agent is context: a P/E of 35 is expensive for a utility and
cheap for a fast grower, so what matters is the position relative to the peer
group, not the absolute number.
"""

import pytest

from app.agents.peer_comparison_agent import PeerComparisonAgent


def ratios(pe=None, pb=None, ps=None, p_fcf=None, net_margin=None,
           operating_margin=None, de=None) -> dict:
    """A TTM ratios payload shaped like FMP's."""
    return {
        "priceToEarningsRatioTTM": pe,
        "priceToBookRatioTTM": pb,
        "priceToSalesRatioTTM": ps,
        "priceToFreeCashFlowRatioTTM": p_fcf,
        "netProfitMarginTTM": net_margin,
        "operatingProfitMarginTTM": operating_margin,
        "debtToEquityRatioTTM": de,
    }


def raw_data(company: dict | None = None, peers: dict | None = None,
             sector_valuation: dict | None = None) -> dict:
    peers = peers if peers is not None else {
        "AAA": ratios(pe=30, pb=8, ps=6, p_fcf=28, net_margin=0.20, operating_margin=0.25, de=0.6),
        "BBB": ratios(pe=40, pb=10, ps=8, p_fcf=35, net_margin=0.25, operating_margin=0.30, de=0.9),
        "CCC": ratios(pe=50, pb=12, ps=10, p_fcf=45, net_margin=0.30, operating_margin=0.35, de=1.2),
    }
    return {
        "ttm": {"ratios": company if company is not None else ratios(
            pe=35, pb=9, ps=7, p_fcf=30, net_margin=0.22, operating_margin=0.28, de=0.8
        )},
        "peers": {
            "companies": [{"symbol": s, "companyName": f"{s} Corp", "mktCap": 1e11} for s in peers],
            "ratios": peers,
        },
        "sector_valuation": sector_valuation if sector_valuation is not None else {
            "sector": "Technology", "industry": "Software",
            "sector_pe": 46.6, "industry_pe": 35.0, "date": "2026-08-14",
        },
    }


def comparison(result: dict, key: str) -> dict:
    return next(c for c in result["comparisons"] if c["key"] == key)


class TestRelativePositioning:
    def test_median_is_used_not_the_mean(self):
        """One extreme peer should not define the benchmark."""
        peers = {
            "AAA": ratios(pe=20), "BBB": ratios(pe=22), "CCC": ratios(pe=24),
            "DDD": ratios(pe=500),
        }
        result = PeerComparisonAgent().run(raw_data(company=ratios(pe=23), peers=peers))
        assert comparison(result, "pe_ratio")["peer_median"] == 23.0

    def test_premium_and_discount_are_reported(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=20), peers={
                "AAA": ratios(pe=40), "BBB": ratios(pe=40), "CCC": ratios(pe=40),
            })
        )
        pe = comparison(result, "pe_ratio")
        assert pe["premium_discount"] == pytest.approx(-0.5)
        assert "below" in pe["verdict"]

    def test_close_to_the_median_reads_as_in_line(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=41), peers={
                "AAA": ratios(pe=40), "BBB": ratios(pe=40), "CCC": ratios(pe=40),
            })
        )
        assert comparison(result, "pe_ratio")["verdict"] == "in line with peers"

    def test_percentile_treats_cheap_as_better_for_multiples(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=10), peers={
                "AAA": ratios(pe=30), "BBB": ratios(pe=40), "CCC": ratios(pe=50),
            })
        )
        assert comparison(result, "pe_ratio")["percentile"] == 100.0

    def test_percentile_treats_fat_as_better_for_margins(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(net_margin=0.40), peers={
                "AAA": ratios(net_margin=0.10), "BBB": ratios(net_margin=0.20),
                "CCC": ratios(net_margin=0.30),
            })
        )
        assert comparison(result, "net_margin")["percentile"] == 100.0


class TestRelativeValuationScore:
    def test_cheaper_than_peers_scores_positive(self):
        cheap = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=15, pb=4, ps=3, p_fcf=14))
        )
        assert cheap["relative_valuation_score"] > 0

    def test_more_expensive_than_peers_scores_negative(self):
        expensive = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=80, pb=25, ps=20, p_fcf=70))
        )
        assert expensive["relative_valuation_score"] < 0

    def test_a_high_multiple_in_a_high_multiple_group_is_not_penalised(self):
        """
        The whole point of the comparison: 35x is not expensive when the peer
        group trades at 40x.
        """
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=35, pb=9, ps=7, p_fcf=30), peers={
                "AAA": ratios(pe=34, pb=9, ps=7, p_fcf=29),
                "BBB": ratios(pe=36, pb=9, ps=7, p_fcf=31),
                "CCC": ratios(pe=40, pb=10, ps=8, p_fcf=33),
            })
        )
        assert abs(result["relative_valuation_score"]) < 0.2

    def test_score_is_bounded(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=1, pb=0.1, ps=0.1, p_fcf=1))
        )
        assert -1.0 <= result["relative_valuation_score"] <= 1.0


class TestDataQuality:
    def test_loss_making_peers_are_excluded_from_multiples(self):
        """A negative P/E means losses, not a cheap stock."""
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=20), peers={
                "AAA": ratios(pe=-15), "BBB": ratios(pe=30), "CCC": ratios(pe=40),
            })
        )
        assert comparison(result, "pe_ratio")["peer_median"] == 35.0

    def test_too_few_comparable_peers_yields_no_median(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe=20), peers={"AAA": ratios(pe=30)})
        )
        assert comparison(result, "pe_ratio")["peer_median"] is None

    def test_no_peers_is_reported_not_crashed(self):
        result = PeerComparisonAgent().run(raw_data(peers={}))
        assert result["peer_count"] == 0
        assert "error" in result
        assert result["relative_valuation_score"] is None

    def test_missing_company_ratios_fall_back_to_computed_metrics(self):
        data = raw_data()
        data["ttm"] = {}
        metrics = {"groups": {"valuation": {"pe_ratio": 25.0, "pb_ratio": 5.0, "ps_ratio": 4.0}}}

        result = PeerComparisonAgent().run(data, metrics)
        assert comparison(result, "pe_ratio")["company"] == 25.0

    def test_malformed_values_are_ignored(self):
        result = PeerComparisonAgent().run(
            raw_data(company=ratios(pe="n/a"), peers={
                "AAA": ratios(pe=None), "BBB": ratios(pe=30), "CCC": ratios(pe=40),
            })
        )
        assert comparison(result, "pe_ratio")["company"] is None

    def test_only_peers_with_data_are_listed(self):
        data = raw_data()
        data["peers"]["companies"].append({"symbol": "ZZZ", "companyName": "No Data Co"})
        result = PeerComparisonAgent().run(data)
        assert "ZZZ" not in [p["symbol"] for p in result["peers"]]


class TestSectorBenchmarks:
    def test_company_pe_is_compared_to_sector_and_industry(self):
        result = PeerComparisonAgent().run(raw_data(company=ratios(pe=70.0)))
        sector = result["sector"]
        # Values are rounded to four decimals for the payload.
        assert sector["vs_sector_pe"] == pytest.approx((70.0 - 46.6) / 46.6, abs=1e-4)
        assert sector["vs_industry_pe"] == pytest.approx((70.0 - 35.0) / 35.0, abs=1e-4)

    def test_missing_snapshot_is_handled(self):
        result = PeerComparisonAgent().run(raw_data(sector_valuation={}))
        assert result["sector"]["sector_pe"] is None
        assert result["sector"]["vs_sector_pe"] is None

    def test_loss_making_company_has_no_sector_comparison(self):
        result = PeerComparisonAgent().run(raw_data(company=ratios(pe=-10.0)))
        assert result["sector"]["vs_sector_pe"] is None


class TestSummary:
    def test_summary_describes_the_stance(self):
        cheap = PeerComparisonAgent().run(raw_data(company=ratios(
            pe=15, pb=4, ps=3, p_fcf=14, operating_margin=0.40)))
        assert "discount" in cheap["summary"]

        expensive = PeerComparisonAgent().run(raw_data(company=ratios(
            pe=90, pb=30, ps=25, p_fcf=80, operating_margin=0.10)))
        assert "premium" in expensive["summary"]

    def test_summary_without_data_says_so(self):
        result = PeerComparisonAgent().run(raw_data(peers={}))
        assert "Not enough comparable data" in result["summary"]
