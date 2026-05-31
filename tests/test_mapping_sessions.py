from __future__ import annotations

from datetime import UTC, datetime, timedelta

from phi_br_core.entities import ENTITY_TO_PLACEHOLDER_PREFIX
from phi_br_core.mapping import PlaceholderIndex
from phi_br_core.sessions import SessionStore


def test_placeholder_index_resolves_multiple_sessions(tmp_path) -> None:
    index = PlaceholderIndex(tmp_path / "index.json")
    index.assign("PACIENTE_001", "phi-a")
    index.assign("CPF_002", "phi-b")

    assert index.resolve(["PACIENTE_001", "CPF_002"]) == {
        "PACIENTE_001": "phi-a",
        "CPF_002": "phi-b",
    }


def test_placeholder_index_persists_assignments(tmp_path) -> None:
    index_path = tmp_path / "index.json"
    PlaceholderIndex(index_path).assign("PACIENTE_001", "phi-a")

    index = PlaceholderIndex(index_path)

    assert index.resolve(["PACIENTE_001"]) == {"PACIENTE_001": "phi-a"}


def test_placeholder_index_allocates_next_global_number_by_prefix(tmp_path) -> None:
    index = PlaceholderIndex(tmp_path / "index.json")
    index.assign("PACIENTE_001", "phi-a")

    assert index.next_key("PACIENTE") == "PACIENTE_002"


def test_placeholder_index_removes_purged_sessions(tmp_path) -> None:
    index = PlaceholderIndex(tmp_path / "index.json")
    index.assign("PACIENTE_001", "phi-expired")
    index.assign("PACIENTE_002", "phi-active")

    index.remove_sessions(["phi-expired"])

    assert index.resolve(["PACIENTE_001"]) == {}
    assert index.resolve(["PACIENTE_002"]) == {"PACIENTE_002": "phi-active"}


def test_placeholder_index_does_not_reuse_numbers_after_purge(tmp_path) -> None:
    index = PlaceholderIndex(tmp_path / "index.json")
    index.assign("PACIENTE_001", "phi-expired")

    index.remove_sessions(["phi-expired"])

    assert index.resolve(["PACIENTE_001"]) == {}
    assert index.next_key("PACIENTE") == "PACIENTE_002"


def test_session_store_creates_metadata_under_session_directory(tmp_path) -> None:
    store = SessionStore(tmp_path)
    now = datetime(2026, 5, 27, 20, 0, tzinfo=UTC)

    session = store.create(source="test", now=now, ttl_hours=24)

    assert session.path == tmp_path / session.session_id
    assert (session.path / "metadata.json").exists()
    assert session.expires_at == now + timedelta(hours=24)


def test_session_store_purges_expired_sessions(tmp_path) -> None:
    store = SessionStore(tmp_path)
    now = datetime(2026, 5, 27, 20, 0, tzinfo=UTC)
    expired = store.create(source="test", now=now - timedelta(hours=25), ttl_hours=24)
    active = store.create(source="test", now=now, ttl_hours=24)

    purged = store.purge_expired(now=now)

    assert expired.session_id in purged
    assert store.session_path(expired.session_id).exists() is False
    assert store.session_path(active.session_id).exists() is True


def test_session_store_can_remove_purged_sessions_from_index(tmp_path) -> None:
    index = PlaceholderIndex(tmp_path / "index.json")
    store = SessionStore(tmp_path, placeholder_index=index)
    now = datetime(2026, 5, 27, 20, 0, tzinfo=UTC)
    expired = store.create(source="test", now=now - timedelta(hours=25), ttl_hours=24)
    active = store.create(source="test", now=now, ttl_hours=24)
    index.assign("PACIENTE_001", expired.session_id)
    index.assign("PACIENTE_002", active.session_id)

    store.purge_expired(now=now)

    assert index.resolve(["PACIENTE_001", "PACIENTE_002"]) == {
        "PACIENTE_002": active.session_id
    }


def test_session_store_sanitizes_source_metadata(tmp_path) -> None:
    store = SessionStore(tmp_path)
    now = datetime(2026, 5, 27, 20, 0, tzinfo=UTC)

    session = store.create(source="Paciente Maria CPF 935.411.347-80", now=now)

    assert session.source == "unknown"


def test_placeholder_prefixes_match_public_contract() -> None:
    assert ENTITY_TO_PLACEHOLDER_PREFIX["BR_AUTHORIZATION_ID"] == "AUTORIZACAO"
    assert ENTITY_TO_PLACEHOLDER_PREFIX["BR_WORKPLACE"] == "LOCAL_TRABALHO"
    assert ENTITY_TO_PLACEHOLDER_PREFIX["BR_CONTEXTUAL_IDENTIFIER"] == (
        "IDENTIFICADOR_CONTEXTUAL"
    )
