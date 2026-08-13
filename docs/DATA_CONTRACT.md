# NHL player-season data contract

## Grain and key

Each source row represents one skater's aggregate statistics for one season across all teams shown
in `Team`. The authoritative key is `(playerId, Season)`; names are display values and are not unique.

The supplied snapshot contains 951 skater rows for season `20222023`. It contains no goalies,
game dates, game type, official roster status, or team-specific statistical splits for traded players.

## Cleaning decisions

- Drop the two empty unnamed export columns and the entirely empty `Shifts/GP` column.
- Drop `MinPerGP` because it duplicates `SecPerGP / 60`.
- Convert the literal `None` to database null for percentage fields.
- Remove control characters from display names without attempting to guess damaged characters.
- Preserve the original comma-separated `Team` value, derive `team_count`, and treat the last token
  as an explicitly inferred season-end team.
- Preserve stars and other legitimate statistical outliers.

## Supported and unsupported analysis

The snapshot supports player leaderboards, penalty-minutes rates, and counts of teams represented in
the source. An inferred season-end roster can use the final team token, but it is not an official or
current active roster.

Exact team totals and league-wide team rankings are not supported by this file because the 95
multi-team players have only combined season totals. Their statistics must not be duplicated across
each listed team. The team rankings endpoint therefore returns clearly labeled lower-bound totals
using only the 856 single-team rows and reports how many multi-team rows were excluded.

## Enforced validation

- Exact 24-column source header, including the two blank header positions.
- Required and unique `(playerId, Season)` values.
- Positions limited to `C`, `D`, `L`, and `R` and teams limited to the 32 source codes.
- Positive games and ice time; nonnegative counting statistics.
- `P = G + A`, `S >= G`, percentages within `[0, 1]`, and `S% = G / S` when shots exist.
- Shooting percentage must be null for zero-shot players.
