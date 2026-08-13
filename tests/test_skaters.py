import unittest

from ingestion.skaters import SkaterStatsIngestor


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_json(self, path, params):
        self.calls.append((path, params))
        start = int(params["start"])
        return self.pages.get(start, {"data": [], "total": 2}), None


class SkaterTests(unittest.TestCase):
    def test_pagination_and_normalization(self):
        summary = {"playerId": 1, "seasonId": 20232024, "gamesPlayed": 2, "goals": 3, "assists": 4,
                   "points": 7, "plusMinus": -1, "penaltyMinutes": 6, "ppGoals": 1, "shGoals": 0,
                   "gameWinningGoals": 1, "shots": 20, "shootingPct": 0.15, "faceoffWinPct": None,
                   "skaterFullName": " Test Player ", "teamAbbrevs": "TST", "positionCode": "C", "ppPoints": 2, "shPoints": 0}
        toi = {"playerId": 1, "timeOnIcePerGame": 600, "shiftsPerGame": 20}
        fake = FakeClient({0: {"data": [summary], "total": 1}})
        ingestor = SkaterStatsIngestor(fake, page_size=1)
        rows = ingestor.normalize_season(ingestor.fetch_season_summary(20232024), [toi])
        self.assertEqual(rows[0].name, "Test Player")
        self.assertEqual(rows[0].minutes_per_game, 10)
        self.assertIsNone(rows[0].faceoff_pct)
        self.assertEqual(rows[0].as_dict()["toi_seconds"], 600)
        self.assertEqual(fake.calls[0][1]["isGame"], "false")

    def test_incomplete_page_fails(self):
        fake = FakeClient({0: {"data": [{"playerId": 1}], "total": 2}})
        with self.assertRaises(ValueError):
            SkaterStatsIngestor(fake).fetch_season_summary(20232024)


if __name__ == "__main__":
    unittest.main()
