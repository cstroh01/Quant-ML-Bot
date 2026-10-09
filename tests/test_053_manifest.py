"""Spec 053 U1: immutable model manifests and verified loading. EXAMPLE — NOT A RESULT."""
import hashlib
import pickle

import pytest

import context  # noqa: F401
from model_registry import ManifestError, load_verified, write_artifact

CONTEXT = dict(algorithm="logistic_l2", algorithm_version="sklearn-1.9.1", seed=7,
               training_cutoff="2025-12-31", feature_schema=["ret_1", "ret_5"], label="open_to_open_direction_1",
               dataset_sha256="a" * 64, membership_sha256="b" * 64, source_tree_hash="c" * 64,
               dependencies={"numpy": "2.5.3", "scikit-learn": "1.9.1"})


def test_round_trip_verifies_every_identity_field(tmp_path):
    manifest = write_artifact(tmp_path, {"coef": [0.1, -0.2]}, **CONTEXT)
    model, loaded = load_verified(tmp_path, expected=CONTEXT)
    assert model == {"coef": [0.1, -0.2]} and loaded == manifest
    assert loaded["artifact_sha256"] == hashlib.sha256((tmp_path / "model.pkl").read_bytes()).hexdigest()


def test_tampered_artifact_bytes_refuse(tmp_path):
    write_artifact(tmp_path, {"coef": [0.1]}, **CONTEXT)
    (tmp_path / "model.pkl").write_bytes(pickle.dumps({"coef": [9.9]}))
    with pytest.raises(ManifestError, match="artifact"):
        load_verified(tmp_path, expected=CONTEXT)


@pytest.mark.parametrize("field,value", [("feature_schema", ["ret_1"]), ("dataset_sha256", "d" * 64),
                                         ("source_tree_hash", "e" * 64), ("label", "close_to_close")])
def test_context_drift_refuses(tmp_path, field, value):
    write_artifact(tmp_path, {"coef": [0.1]}, **CONTEXT)
    with pytest.raises(ManifestError, match=field):
        load_verified(tmp_path, expected=CONTEXT | {field: value})


def test_manifest_is_immutable_once_written(tmp_path):
    write_artifact(tmp_path, {"coef": [0.1]}, **CONTEXT)
    with pytest.raises(ManifestError, match="exists"):
        write_artifact(tmp_path, {"coef": [0.2]}, **CONTEXT)


@pytest.mark.parametrize("field", ["dataset_sha256", "training_cutoff", "seed"])
def test_incomplete_context_refuses_to_write(tmp_path, field):
    bad = dict(CONTEXT); bad.pop(field)
    with pytest.raises(ManifestError, match=field):
        write_artifact(tmp_path, {"coef": [0.1]}, **bad)


@pytest.mark.parametrize("expected", [{}, {f: CONTEXT[f] for f in CONTEXT if f != "seed"}])
def test_partial_expected_context_refuses_before_unpickling(tmp_path, expected, monkeypatch):
    write_artifact(tmp_path, {"coef": [0.1]}, **CONTEXT)
    import model_registry
    monkeypatch.setattr(model_registry.pickle, "loads", lambda _b: pytest.fail("unpickled before verification"))
    with pytest.raises(ManifestError, match="expected context missing"):
        load_verified(tmp_path, expected=expected)
