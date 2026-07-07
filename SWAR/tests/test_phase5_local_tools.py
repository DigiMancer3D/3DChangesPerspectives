from swar.local_tools import SimpleSpellChecker, find_matches


def test_find_matches_line_column_case_insensitive():
    text = "Alpha beta\nsecond Alpha"
    matches = find_matches(text, "alpha")
    assert len(matches) == 2
    assert matches[0].line == 1 and matches[0].column == 1
    assert matches[1].line == 2 and matches[1].column == 8


def test_find_matches_case_sensitive():
    assert len(find_matches("Alpha alpha", "Alpha", case_sensitive=True)) == 1


def test_spell_checker_skips_urls_and_marks_unknown_words():
    checker = SimpleSpellChecker(words={"hello", "world"})
    assert list(checker.iter_unknown("https://example.com strangeword")) == []
    unknown = list(checker.iter_unknown("hello strangeword world"))
    assert unknown and unknown[0][2] == "strangeword"
