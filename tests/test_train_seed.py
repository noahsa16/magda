"""Der Seed muss schon für den neu initialisierten Klassifikationskopf gelten."""

from types import SimpleNamespace

import torch

from magda.cli import train


def test_kopf_initialisierung_ist_bei_gleichem_seed_wiederholbar(monkeypatch, tmp_path):
    heads = []

    def initialize(*args, **kwargs):
        heads.append(torch.rand(8))
        return object()

    monkeypatch.setattr(train, "build_datasets", lambda *args: ("local", [], []))
    monkeypatch.setattr(train, "CHECKPOINTS_DIR", tmp_path)
    monkeypatch.setattr(train.AutoModelForTokenClassification, "from_pretrained", initialize)
    monkeypatch.setattr(train.AutoTokenizer, "from_pretrained", lambda *args: SimpleNamespace(save_pretrained=lambda *args: None))
    monkeypatch.setattr(train, "TrainingArguments", lambda **kwargs: kwargs)
    monkeypatch.setattr(train, "Trainer", lambda **kwargs: SimpleNamespace(train=lambda: None, save_model=lambda *args: None))
    train.main(["gbert"])
    train.main(["gbert"])
    assert torch.equal(heads[0], heads[1])
