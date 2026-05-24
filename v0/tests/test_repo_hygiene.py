from pathlib import Path


def test_package_imports():
    import ai_tamperguard

    assert ai_tamperguard.__version__


def test_private_paths_are_gitignored():
    gitignore = Path(".gitignore").read_text()
    for path in [
        "data/private/",
        "models/private/",
        "reports/private/",
        "splunk/private/",
    ]:
        assert path in gitignore
