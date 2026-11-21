import ingestion


def test_version_is_a_string() -> None:
    assert isinstance(ingestion.__version__, str)
