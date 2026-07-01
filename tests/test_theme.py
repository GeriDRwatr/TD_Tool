import json

from app import theme as theme_module
from app.theme import Theme, ThemeManager


def _isolated_manager(monkeypatch, tmp_path):
    theme_file = tmp_path / "theme.json"
    monkeypatch.setattr(theme_module, "_THEME_FILE", str(theme_file))
    return ThemeManager(), theme_file


def test_new_manager_uses_default_theme(monkeypatch, tmp_path):
    mgr, _ = _isolated_manager(monkeypatch, tmp_path)

    assert mgr.get() == Theme()


def test_update_changes_theme_and_notifies_listeners(monkeypatch, tmp_path):
    mgr, _ = _isolated_manager(monkeypatch, tmp_path)
    calls = []
    mgr.add_listener(lambda: calls.append(1))

    mgr.update(bg_main="#000000")

    assert mgr.get().bg_main == "#000000"
    assert calls == [1]


def test_update_ignores_unknown_keys(monkeypatch, tmp_path):
    mgr, _ = _isolated_manager(monkeypatch, tmp_path)

    mgr.update(not_a_real_field="whatever")

    assert not hasattr(mgr.get(), "not_a_real_field")


def test_save_then_load_roundtrips_theme(monkeypatch, tmp_path):
    mgr, theme_file = _isolated_manager(monkeypatch, tmp_path)
    mgr.update(bg_main="#123456", icon_size=99)
    mgr.save()

    assert theme_file.exists()
    on_disk = json.loads(theme_file.read_text())
    assert on_disk["bg_main"] == "#123456"

    mgr2 = ThemeManager()
    assert mgr2.get().bg_main == "#123456"
    assert mgr2.get().icon_size == 99


def test_load_falls_back_to_defaults_on_corrupt_file(monkeypatch, tmp_path):
    theme_file = tmp_path / "theme.json"
    theme_file.write_text("{not valid json")
    monkeypatch.setattr(theme_module, "_THEME_FILE", str(theme_file))

    mgr = ThemeManager()

    assert mgr.get() == Theme()


def test_reset_restores_defaults_and_notifies(monkeypatch, tmp_path):
    mgr, _ = _isolated_manager(monkeypatch, tmp_path)
    mgr.update(bg_main="#abcdef")
    calls = []
    mgr.add_listener(lambda: calls.append(1))

    mgr.reset()

    assert mgr.get() == Theme()
    assert calls == [1]


def test_notify_isolates_listener_exceptions(monkeypatch, tmp_path):
    mgr, _ = _isolated_manager(monkeypatch, tmp_path)
    calls = []
    mgr.add_listener(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    mgr.add_listener(lambda: calls.append("second"))

    mgr.update(bg_main="#111111")   # не повинно кидати виняток

    assert calls == ["second"]
