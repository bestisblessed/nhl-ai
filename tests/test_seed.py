import unittest
from pathlib import Path

from ingestion.seed import load_seed_csv


class SeedImportTests(unittest.TestCase):
    def test_seed_preserves_blank_positions_and_none(self):
        rows = load_seed_csv(Path(__file__).parents[1] / "data" / "data_dump.csv")
        self.assertEqual(len(rows), 951)
        abr = next(row for row in rows if row.name == "Nick Abruzzese")
        self.assertIsNone(abr.blank_1)
        self.assertIsNone(abr.blank_2)
        self.assertIsNone(abr.shifts_per_game)
        self.assertIsNone(abr.faceoff_pct)
        self.assertEqual(abr.season_id, 20222023)

    def test_wrong_season_fails(self):
        with self.assertRaises(ValueError):
            load_seed_csv(Path(__file__).parents[1] / "data" / "data_dump.csv", expected_season_id=20232024)


if __name__ == "__main__":
    unittest.main()
