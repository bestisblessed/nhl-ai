from ingestion.games import GameIngestor, ScoreIngestor
from ingestion.teams import (
    TeamIngestor,
    validate_preseason_empty,
)
from ingestion.rosters import RosterIngestor
from ingestion.standings import StandingsIngestor


class FakeClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append((path, params))
        value = self.payloads[path]
        return value, {"test": True}


def test_game_and_team_stats_parse_and_use_correct_filters():
    client = FakeClient({
        "/stats/rest/en/game": {"total": 1, "data": [{
            "id": 2024020001, "season": 20242025, "gameType": 2, "gameDate": "2024-10-04",
            "easternStartTime": "2024-10-04T13:00:00", "gameNumber": 1,
            "gameScheduleStateId": 1, "gameStateId": 7, "homeTeamId": 7,
            "visitingTeamId": 1, "homeScore": 1, "visitingScore": 4, "period": 3,
        }]},
        "/stats/rest/en/team/summary": {"total": 1, "data": [{
            "gameId": 2024020001, "teamId": 7, "gameDate": "2024-10-04", "homeRoad": "H",
            "opponentTeamAbbrev": "EDM", "gamesPlayed": 1, "goalsFor": 1,
            "goalsAgainst": 4, "shotsForPerGame": 26, "shotsAgainstPerGame": 31,
            "wins": 0, "losses": 1, "otLosses": 0, "points": 0,
        }]},
    })
    game = GameIngestor(client).fetch_season(20242025)
    team = TeamIngestor(client).fetch_games(20242025)
    assert game[0].game_id == team[0].game_id == 2024020001
    assert game[0].home_team_id == 7 and team[0].shots_for_per_game == 26.0
    assert "season=20242025 and gameType=2" in client.calls[0][1]["cayenneExp"]


def test_score_roster_and_standings_flatten_web_payloads():
    client = FakeClient({
        "/v1/score/2025-04-17": {"games": [{
            "id": 2024021307, "season": 20242025, "gameType": 2, "gameDate": "2025-04-17",
            "startTimeUTC": "2025-04-17T23:00:00Z", "gameState": "OFF", "gameScheduleState": "OK",
            "awayTeam": {"id": 4, "abbrev": "PHI", "score": 4, "sog": 24},
            "homeTeam": {"id": 7, "abbrev": "BUF", "score": 5, "sog": 31},
        }]},
        "/v1/roster/TBL/current": {"forwards": [{"id": 8478519, "firstName": {"default": "Anthony"},
            "lastName": {"default": "Cirelli"}, "positionCode": "C", "sweaterNumber": 71}],
            "defensemen": [], "goalies": [{"id": 8476899, "firstName": {"default": "Andrei"},
            "lastName": {"default": "Vasilevskiy"}, "positionCode": "G"}]},
        "/v1/standings/2025-04-17": {"standings": [{"seasonId": 20242025, "gameTypeId": 2,
            "teamAbbrev": {"default": "WPG"}, "teamName": {"default": "Winnipeg Jets"},
            "gamesPlayed": 82, "wins": 56, "losses": 22, "otLosses": 4, "points": 116,
            "goalFor": 277, "goalAgainst": 191, "goalDifferential": 86}]},
    })
    score = ScoreIngestor(client).fetch_date("2025-04-17")[0]
    roster = RosterIngestor(client).fetch_current("TBL", snapshot_date="2026-08-13")
    standings = StandingsIngestor(client).fetch_date("2025-04-17")[0]
    assert (score.home_score, score.visiting_sog) == (5, 24)
    assert {r.player_id for r in roster} == {8478519, 8476899}
    assert standings.team_abbrev == "WPG" and standings.team_id is None


def test_preseason_empty_is_valid_until_a_final_game_exists():
    validate_preseason_empty(season_id=20262027, final_game_count=0, stat_records=[])
    try:
        validate_preseason_empty(season_id=20262027, final_game_count=1, stat_records=[])
    except ValueError as exc:
        assert "no statistics" in str(exc)
    else:
        raise AssertionError("final games with empty stats must fail")
