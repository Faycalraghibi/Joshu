from wordcount import main


def run(capsys, tmp_path, *flags):
    path = tmp_path / "in.txt"
    path.write_text("b a b c b a", encoding="utf-8")
    main([str(path), *flags])
    return capsys.readouterr().out.split("\n")[:3]


def test_default_order(capsys, tmp_path):
    assert run(capsys, tmp_path) == ["b 3", "a 2", "c 1"]


def test_reverse(capsys, tmp_path):
    assert run(capsys, tmp_path, "--reverse") == ["c 1", "a 2", "b 3"]
