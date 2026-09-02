from findmyjob.config import Settings


def test_database_url_derived_from_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    settings = Settings()
    assert settings.database_url == f"sqlite:///{(tmp_path / 'findmyjob.db').as_posix()}"


def test_database_url_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_URL", "sqlite:///custom.db")
    assert Settings().database_url == "sqlite:///custom.db"


def test_ensure_dirs_creates_all_subdirs(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "d"))
    settings = Settings()
    settings.ensure_dirs()
    for path in (
        settings.documents_dir,
        settings.letters_dir,
        settings.models_dir,
        settings.logs_dir,
        settings.backups_dir,
    ):
        assert path.is_dir()
