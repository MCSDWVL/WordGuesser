# Fake Words

A static five-round daily browser game. The browser has no API dependency: it loads a generated `data/game-data.json` file and uses a UTC-date seed (or `?seed=anything`) to choose a reproducible game.

## Build game data

The data builder consumes the local Wiktextract dump and does not use the sibling Scrabble-like files.

```powershell
python -m pip install -r requirements.txt
python scripts/build_game_data.py --input ..\Lexicon\raw-wiktextract-data.jsonl
```

It streams the raw dump once and writes three ignored local artifacts under `data/`:

- `word-candidates.jsonl` — all eligible real-word candidates, including `word`, `definition`, `zipf`, and Wiktextract usage `tags` for editorial review.
- `known-words.json` — normalized English Wiktextract words/forms used only to prevent fake-word collisions.
- `frequency-report.json` — Zipf buckets and selected examples for tuning.
- `game-data.json` — the compact browser asset: 25,000 real words plus 25,000 generated fakes.

After that first full run, tune the real-word pool without rereading Wiktextract, for example:

```powershell
python scripts/build_game_data.py --candidates-input data\word-candidates.jsonl --min-zipf 1.5 --max-zipf 2.4 --seed review-1
```

Higher Zipf values generally mean more familiar words. The default 1.5–3.5 range is intentionally uncommon but should be reviewed before publishing. `--word-count` is a maximum, not a requirement: if a Zipf range contains fewer candidates, the builder writes all available words and prints a warning. The builder excludes usage labels such as archaic, obsolete, rare, vulgar, and offensive, then creates fakes using a seeded character-trigram model. Every fake is checked against all normalized English Wiktextract headwords and recorded forms.

Serve the folder over HTTP after generating data, for example with `python -m http.server`, then open the shown local URL. Opening `index.html` directly will not permit the browser to fetch JSON.

## Verification

```powershell
npm test
```

## Attribution

Definitions are derived from Wiktionary/Wiktextract data. Before public deployment, include the exact source snapshot, attribution text, and applicable Wiktionary/Wiktextract and `wordfreq` licenses with the distributed game data.
