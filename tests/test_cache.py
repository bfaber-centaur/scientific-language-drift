"""Revision-keyed, hash-verified cache (fix for the V1 revision-cache collision)."""
import hashlib
import os

import pytest

from mlngrams import load

A = "a" * 40
B = "b" * 40


@pytest.fixture
def fake_hub(tmp_path, monkeypatch):
    """Two revisions of one file with different bytes; no network."""
    blobs = {A: b"bytes at revision A", B: b"bytes at revision B"}
    calls = []
    monkeypatch.setattr(load, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(load, "expected_sha256", lambda rel, rev: hashlib.sha256(blobs[rev]).hexdigest())

    def download(url, dst):
        rev = url.split("/resolve/")[1].split("/")[0]
        calls.append(rev)
        with open(dst, "wb") as f:
            f.write(blobs[rev])

    monkeypatch.setattr(load, "_download", download)
    return blobs, calls


def test_revisions_do_not_collide(fake_hub):
    blobs, calls = fake_hub
    pa = load.fetch("direct", "iclr", 2024, revision=A)
    pb = load.fetch("direct", "iclr", 2024, revision=B)
    assert pa != pb
    assert open(pa, "rb").read() == blobs[A]
    assert open(pb, "rb").read() == blobs[B]
    load.fetch("direct", "iclr", 2024, revision=A)  # cache hit
    assert calls == [A, B]


def test_legacy_unkeyed_cache_is_ignored(fake_hub, tmp_path):
    """The V1 MRE: bytes at <cache>/direct/iclr-2024.parquet must not be served for another revision."""
    blobs, _ = fake_hub
    legacy = tmp_path / "direct" / "iclr-2024.parquet"
    legacy.parent.mkdir()
    legacy.write_bytes(b"cached bytes from revision A")
    got = load.fetch("direct", "iclr", 2024, revision=B)
    assert open(got, "rb").read() == blobs[B]


def test_hash_mismatch_is_rejected(fake_hub, monkeypatch):
    monkeypatch.setattr(load, "expected_sha256", lambda rel, rev: "0" * 64)
    with pytest.raises(load.CacheIntegrityError):
        load.fetch("direct", "iclr", 2024, revision=A)
    assert not os.path.exists(load.cache_path("direct", "iclr", 2024, A))


def test_tampered_cache_detected_when_verifying(fake_hub, monkeypatch):
    p = load.fetch("direct", "iclr", 2024, revision=A)
    with open(p, "r+b") as f:
        f.write(b"X")  # same size, different bytes
    monkeypatch.setenv("MLNGRAMS_VERIFY", "1")
    with pytest.raises(load.CacheIntegrityError):
        load.fetch("direct", "iclr", 2024, revision=A)


def test_truncated_cache_detected(fake_hub):
    p = load.fetch("direct", "iclr", 2024, revision=A)
    with open(p, "ab") as f:
        f.write(b"extra")
    with pytest.raises(load.CacheIntegrityError):
        load.fetch("direct", "iclr", 2024, revision=A)


def test_branch_names_are_resolved(fake_hub, monkeypatch):
    monkeypatch.setattr(load, "resolve_revision", lambda r: A if r == "main" else r)
    assert load.fetch("direct", "iclr", 2024, revision="main") == load.cache_path("direct", "iclr", 2024, A)
