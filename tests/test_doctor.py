import argparse

import pytest

from findmyjob.cli import cmd_models_fetch
from findmyjob.services.doctor import run_doctor

pytestmark = pytest.mark.usefixtures("seeded_session")


def test_doctor_runs_and_returns_bool(capsys):
    result = run_doctor()
    assert isinstance(result, bool)
    out = capsys.readouterr().out
    assert "python >= 3.12" in out
    assert "migrations at head" in out


def test_models_fetch_ok(monkeypatch, capsys):
    class FakeEmbedder:
        model_version = "fake"
        dim = 4

    monkeypatch.setattr("findmyjob.services.embeddings.get_embedder", lambda: FakeEmbedder())
    assert cmd_models_fetch(argparse.Namespace()) == 0
    assert "ready" in capsys.readouterr().out


def test_models_fetch_unavailable(monkeypatch, capsys):
    monkeypatch.setattr("findmyjob.services.embeddings.get_embedder", lambda: None)
    assert cmd_models_fetch(argparse.Namespace()) == 1
