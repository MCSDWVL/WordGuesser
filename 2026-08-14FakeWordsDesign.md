# Fake Words
Fake words is a static browser game implemented in HTML and javascript.

The game proceeds in 5 rounds with a daily seed (seed should be exposed to change for testing).

In each round, the player is shown a word, and has to guess if it is a real or a fake word.

They are scored correct answers out of 5.

After each word, if it is real, they should be given the definition, and if it is fake, they should be told it was fake.

# Building the Word List
We need to form a plan to build the word list, which has "exotic" real english words and their definitions,
as well as a list of "plausible" fake words.

We should consider both methods for generating fake words in bulk ahead of time, or for spontaneously generating
them during play. Please evaluate both options and propose a solution.

## Data Sources
There are several files with dictionaries of words in the relative folder ../Lexicon/

Some key files in there:
- dictionary.txt - a raw list of words that are valid to play in scrabble
- lexicon.csv - a csv file of words with markers indicating some properties
- raw-wiktextract-data.jsonl - a json dump of a wiktionary text
- some python scripts for generating csvs from the json which we may want to immitate
