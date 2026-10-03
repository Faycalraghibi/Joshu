from text_utils import slugify


def test_basic():
    assert slugify("Hello World") == "hello-world"


def test_punctuation_and_spaces():
    assert slugify("  Joshu: an AI agent!  ") == "joshu-an-ai-agent"


def test_accents():
    assert slugify("Café Déjà Vu") == "cafe-deja-vu"
