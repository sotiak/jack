import pytest

from jack import main


def test_main_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    main()

    assert capsys.readouterr().out == "Hello from jack!\n"
