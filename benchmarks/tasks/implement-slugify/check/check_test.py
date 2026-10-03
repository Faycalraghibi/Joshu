from text_utils import slugify


def test_hidden_cases():
    assert slugify("Multiple   ---   separators") == "multiple-separators"
    assert slugify("Numbers 2026 and v3.8") == "numbers-2026-and-v3-8"
    assert slugify("") == ""
    assert slugify("Ünïcödé") == "unicode"
