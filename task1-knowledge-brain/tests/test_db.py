from app import db


def test_connect_sets_finite_socket_timeout(monkeypatch):
    seen = {}

    def fake_connection(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(db.pg8000.native, "Connection", fake_connection)
    db.connect("postgresql://demo:secret@localhost:55432/kb", timeout=4.5)
    assert seen["timeout"] == 4.5
    assert seen["host"] == "localhost"
    assert seen["port"] == 55432
