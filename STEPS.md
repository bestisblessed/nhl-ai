Q: so what would be the first few things from the assignment/plan to get working in simpler english/sentence or two for each step? Getting the scraper working? What specifically?

A:
Yes—the scraper is an early step, but the very first goal is proving the whole application can move data from a source into the database and return it through the API.
Get the supplied CSV into the database
Build the database and importer first. Clean data_dump.csv, insert its 951 players for 2022-23, and prove the import produces consistent results every time.
Answer one assignment question through FastAPI
Create the first API route—for example, “Which player scored the most goals?” It should query PostgreSQL and return Connor McDavid with 64 goals. This proves the CSV, database, and API work together.
Build the first NHL API scraper
Start with the NHL skater season-summary endpoint. Fetch 2023-24, convert its fields into the same format as the supplied CSV, and load its 924 skaters without changing the original 2022-23 data.
Expand the scraper across every season
Run the same process for 2024-25, 2025-26, and 2026-27. The first three should contain data; 2026-27 should be recorded as an upcoming season with zero skater statistics until regular-season games begin.
Add games and team game logs
Scrape the NHL games endpoint for the complete schedules, then the team-summary game endpoint for goals, shots, scores, and opponents. This supplies the data needed to rank teams accurately and show team game logs.
Add the remaining assignment routes
Implement player goal leaders, penalties per minute, team goals/shots rankings, players who appeared for multiple teams, schedules, standings, and current rosters. Keep each route querying normalized database tables rather than reading CSV files directly.
Turn it into a daily updater
Create one command that checks the previous three days for new or corrected games, updates the current season, validates the results, and leaves the previous good database state untouched if anything fails.
Package and prove it
Run the API, PostgreSQL, importer, and scraper through Docker Compose. Add tests for the known 2022-23 answers, missing seasons, duplicate imports, and the valid empty 2026-27 preseason state.
The first practical milestone should therefore be:
Import the supplied CSV → query it through FastAPI → scrape and load 2023-24 skaters.

Once that works cleanly, expanding to the other seasons and datasets becomes repetitive rather than risky.
Follow-up:
Show me the exact folder and file structure for this first milestone.
Give me the database tables needed for the CSV import and skater scraper.
Write the implementation checklist for the CSV-to-FastAPI vertical slice.
Explain the exact NHL skater endpoint and how each response field maps to the CSV.
