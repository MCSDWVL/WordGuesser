#!/usr/bin/env python3
"""Create review data and static browser assets from an English Wiktextract JSONL dump.

The script never uploads the source dump. It streams it once, so the 21 GB input
does not need to fit in memory; only normalized word sets and eligible entries do.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from wordfreq import zipf_frequency
except ImportError as exc:  # pragma: no cover - environment error
    raise SystemExit("Missing dependency: run `python -m pip install -r requirements.txt`.") from exc

WORD_RE = re.compile(r"^[a-z]{5,11}$")
BLOCKED_TAGS = {"archaic", "obsolete", "rare", "offensive", "vulgar", "dated"}
SKIP_POS = {"name", "character", "symbol", "suffix", "prefix", "infix", "phrase"}


def normalized_word(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    word = value.strip().lower()
    return word if WORD_RE.fullmatch(word) else None


def english_entry(entry: dict[str, Any]) -> bool:
    return str(entry.get("lang", "")).lower() in {"english", "en"}


def tags_for(entry: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for sense in entry.get("senses") or []:
        if isinstance(sense, dict):
            tags.update(str(tag).lower() for tag in (sense.get("tags") or []))
    return tags


def first_definition(entry: dict[str, Any]) -> str | None:
    for sense in entry.get("senses") or []:
        if not isinstance(sense, dict) or sense.get("form_of") or sense.get("alt_of"):
            continue
        for gloss in sense.get("glosses") or []:
            if isinstance(gloss, str):
                clean = " ".join(gloss.split())
                if clean and len(clean) <= 350:
                    return clean
    return None


def iter_known_forms(entry: dict[str, Any]) -> Iterable[str]:
    word = normalized_word(entry.get("word"))
    if word:
        yield word
    for form in entry.get("forms") or []:
        if isinstance(form, dict):
            normalized = normalized_word(form.get("form") or form.get("word"))
            if normalized:
                yield normalized


def collect_candidates(input_path: Path) -> tuple[set[str], dict[str, dict[str, Any]]]:
    known_words: set[str] = set()
    candidates: dict[str, dict[str, Any]] = {}
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or not english_entry(entry):
                continue
            known_words.update(iter_known_forms(entry))
            word = normalized_word(entry.get("word"))
            tags = tags_for(entry)
            definition = first_definition(entry)
            pos = str(entry.get("pos", "")).lower()
            is_lemma = not entry.get("form_of") and all(
                not isinstance(sense, dict) or not sense.get("form_of")
                for sense in (entry.get("senses") or [])
            )
            if not word or not definition or not is_lemma or pos in SKIP_POS or tags & BLOCKED_TAGS:
                continue
            zipf = round(zipf_frequency(word, "en"), 2)
            candidate = {"word": word, "definition": definition, "zipf": zipf, "tags": sorted(tags)}
            # Prefer the shortest clean definition when an entry has multiple POS records.
            existing = candidates.get(word)
            if existing is None or len(definition) < len(existing["definition"]):
                candidates[word] = candidate
            if line_number % 1_000_000 == 0:
                print(f"Processed {line_number:,} lines; {len(candidates):,} eligible candidates.")
    return known_words, candidates


def write_candidates(path: Path, candidates: dict[str, dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for word in sorted(candidates):
            output.write(json.dumps(candidates[word], ensure_ascii=False, separators=(",", ":")) + "\n")


def load_candidates(path: Path) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            entry = json.loads(line)
            if isinstance(entry, dict) and isinstance(entry.get("word"), str):
                candidates[entry["word"]] = entry
    return candidates


def choose_words(candidates: dict[str, dict[str, Any]], minimum: float, maximum: float, count: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = [entry for entry in candidates.values() if entry["zipf"] > 0 and minimum <= entry["zipf"] <= maximum]
    if len(pool) < count:
        print(f"Warning: only {len(pool):,} words in Zipf range {minimum}-{maximum}; using all of them instead of the requested {count:,}.")
    rng.shuffle(pool)
    return sorted(pool[:count], key=lambda entry: entry["word"])


def trigram_transitions(words: Iterable[str]) -> dict[str, tuple[list[str], list[int]]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for word in words:
        padded = f"^^{word}$"
        for index in range(len(padded) - 2):
            counts[padded[index:index + 2]][padded[index + 2]] += 1
    return {state: (list(counter), list(counter.values())) for state, counter in counts.items()}


def generate_fake_words(real_words: list[dict[str, Any]], known_words: set[str], count: int, rng: random.Random) -> list[str]:
    transitions = trigram_transitions(entry["word"] for entry in real_words)
    lengths = [len(entry["word"]) for entry in real_words]
    fakes: set[str] = set()
    attempts = 0
    while len(fakes) < count:
        attempts += 1
        if attempts > count * 500:
            raise RuntimeError("Could not generate enough collision-free fake words.")
        target_length = rng.choice(lengths)
        state = "^^"
        letters: list[str] = []
        while len(letters) < target_length:
            options = transitions.get(state)
            if not options:
                break
            symbols, weights = options
            allowed = [(symbol, weight) for symbol, weight in zip(symbols, weights) if symbol != "$"]
            if not allowed:
                break
            symbol = rng.choices([item[0] for item in allowed], [item[1] for item in allowed])[0]
            letters.append(symbol)
            state = state[1] + symbol
        word = "".join(letters)
        if (WORD_RE.fullmatch(word) and word not in known_words and word not in fakes
                and not re.search(r"(.)\1\1", word)):
            fakes.add(word)
    return sorted(fakes)


def write_report(path: Path, candidates: dict[str, dict[str, Any]], selected: list[dict[str, Any]], minimum: float, maximum: float) -> None:
    buckets = Counter(f"{int(entry['zipf'])}-{int(entry['zipf']) + 1}" for entry in candidates.values() if entry["zipf"] > 0)
    samples = sorted(selected, key=lambda entry: entry["zipf"])[:10] + sorted(selected, key=lambda entry: entry["zipf"])[-10:]
    path.write_text(json.dumps({"selection_range": [minimum, maximum], "eligible_by_zipf_bucket": buckets, "selected_samples": samples}, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Path to raw Wiktextract JSONL.")
    source.add_argument("--candidates-input", type=Path, help="Previously generated word-candidates.jsonl; avoids rereading Wiktextract.")
    parser.add_argument("--known-words-input", type=Path, help="Known-word JSON produced alongside candidate data.")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--min-zipf", type=float, default=1.5)
    parser.add_argument("--max-zipf", type=float, default=3.5)
    parser.add_argument("--word-count", type=int, default=25_000)
    parser.add_argument("--fake-count", type=int, default=25_000)
    parser.add_argument("--seed", default="fake-words-v1")
    args = parser.parse_args()
    if args.min_zipf >= args.max_zipf:
        parser.error("--min-zipf must be lower than --max-zipf")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = args.output_dir / "word-candidates.jsonl"
    known_words_path = args.output_dir / "known-words.json"
    if args.input:
        known_words, candidates = collect_candidates(args.input)
        write_candidates(candidates_path, candidates)
        known_words_path.write_text(json.dumps(sorted(known_words), separators=(",", ":")), encoding="utf-8")
    else:
        candidates = load_candidates(args.candidates_input)
        known_source = args.known_words_input or known_words_path
        if not known_source.exists():
            parser.error(f"Known-word data not found: {known_source}. Pass --known-words-input.")
        known_words = set(json.loads(known_source.read_text(encoding="utf-8")))
    rng = random.Random(args.seed)
    selected = choose_words(candidates, args.min_zipf, args.max_zipf, args.word_count, rng)
    fakes = generate_fake_words(selected, known_words, args.fake_count, rng)
    payload = {"metadata": {"source": "Wiktextract English", "seed": args.seed, "zipf_range": [args.min_zipf, args.max_zipf]}, "words": selected, "fakes": fakes}
    (args.output_dir / "game-data.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_report(args.output_dir / "frequency-report.json", candidates, selected, args.min_zipf, args.max_zipf)
    print(f"Wrote {len(candidates):,} candidates, {len(selected):,} real words, and {len(fakes):,} fakes to {args.output_dir}.")


if __name__ == "__main__":
    main()
