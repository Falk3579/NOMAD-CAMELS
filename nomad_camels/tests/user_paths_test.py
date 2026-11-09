"""Tests for user-owned configuration files and migration from older installs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from nomad_camels.utility import user_paths


@pytest.fixture
def isolated_paths(monkeypatch, tmp_path: Path):
    """Keep tests independent of the developer's actual config and package."""
    home = tmp_path / "user-config"
    legacy = tmp_path / "installed-package"
    legacy.mkdir()
    monkeypatch.setattr(user_paths, "user_config_root", lambda: home)
    monkeypatch.setattr(user_paths, "_legacy_package_root", lambda: legacy)
    return home, legacy


def test_fresh_config_pointer_uses_user_directory(isolated_paths, tmp_path):
    home, package = isolated_paths
    custom = tmp_path / "custom-config"

    assert user_paths.read_config_pointer() is None
    user_paths.write_config_pointer(custom)

    assert user_paths.read_config_pointer() == str(custom)
    assert (home / "config_path").read_text(encoding="utf-8") == str(custom)
    assert not (package / "config_path").exists()


def test_existing_custom_config_path_is_migrated_without_moving_data(
    isolated_paths, tmp_path
):
    home, package = isolated_paths
    custom = tmp_path / "user-selected-location"
    custom.mkdir()
    settings = custom / "preferences.json"
    settings.write_text('{"theme": "preserved"}', encoding="utf-8")
    (package / "config_path").write_text(str(custom), encoding="utf-8")

    assert user_paths.read_config_pointer() == str(custom)
    assert (home / "config_path").read_text(encoding="utf-8") == str(custom)
    assert settings.read_text(encoding="utf-8") == '{"theme": "preserved"}'
    assert (package / "config_path").read_text(encoding="utf-8") == str(custom)


def test_existing_new_config_pointer_wins_over_legacy(isolated_paths, tmp_path):
    home, package = isolated_paths
    (package / "config_path").write_text("obsolete-path", encoding="utf-8")
    chosen = tmp_path / "preferred-config"
    user_paths.write_config_pointer(chosen)

    assert user_paths.read_config_pointer() == str(chosen)
    assert (home / "config_path").read_text(encoding="utf-8") == str(chosen)


def test_legacy_startup_cache_migrates_and_new_cache_takes_precedence(isolated_paths):
    home, package = isolated_paths
    old = package / "startup_packages.txt"
    old.write_text("alpha\nbeta\n", encoding="utf-8")

    assert user_paths.read_startup_packages() == ["alpha", "beta"]
    assert (home / "startup_packages.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"

    old.write_text("obsolete\n", encoding="utf-8")
    assert user_paths.read_startup_packages() == ["alpha", "beta"]


def test_startup_cache_writes_only_into_user_directory(isolated_paths):
    home, package = isolated_paths

    user_paths.write_startup_packages(["alpha", "_private", "beta"])
    user_paths.write_startup_packages(["different"])
    assert (home / "startup_packages.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert not (package / "startup_packages.txt").exists()


def test_unwritable_startup_cache_is_not_a_startup_error(
    isolated_paths, monkeypatch, caplog
):
    def unwritable(*args, **kwargs):
        raise PermissionError("read-only user directory")

    monkeypatch.setattr(user_paths, "_atomic_write", unwritable)
    user_paths.write_startup_packages(["alpha"])

    assert "Could not save startup package cache" in caplog.text
    assert user_paths.read_startup_packages() == []


def test_unwritable_legacy_cache_migration_still_reads_cache(
    isolated_paths, monkeypatch, caplog
):
    _, package = isolated_paths
    (package / "startup_packages.txt").write_text("legacy-package\n", encoding="utf-8")

    def unwritable(*args, **kwargs):
        raise PermissionError("read-only user directory")

    monkeypatch.setattr(user_paths, "_atomic_write", unwritable)
    assert user_paths.read_startup_packages() == ["legacy-package"]
    assert "Could not migrate startup package cache" in caplog.text


def test_config_pointer_atomic_failure_keeps_previous_value(
    isolated_paths, monkeypatch
):
    home, _ = isolated_paths
    user_paths.write_config_pointer("existing-directory")

    def failed_replace(*args, **kwargs):
        raise OSError("cannot atomically replace")

    monkeypatch.setattr(user_paths.os, "replace", failed_replace)
    with pytest.raises(OSError, match="cannot atomically replace"):
        user_paths.write_config_pointer("new-directory")
    assert (home / "config_path").read_text(encoding="utf-8") == "existing-directory"
    assert list(home.glob(".config_path.*")) == []


def test_migration_failure_still_uses_legacy_pointer(isolated_paths, monkeypatch):
    home, package = isolated_paths
    (package / "config_path").write_text("existing-user-config", encoding="utf-8")

    def unwritable(*args, **kwargs):
        raise PermissionError("read-only user directory")

    monkeypatch.setattr(user_paths, "_atomic_write", unwritable)
    assert user_paths.read_config_pointer() == "existing-user-config"
    assert not (home / "config_path").exists()


def test_load_save_preferences_preserves_migrated_custom_location(
    isolated_paths, tmp_path, monkeypatch
):
    """Exercise the actual preference loader, not only the path helper."""
    from nomad_camels.utility import load_save_functions as settings

    home, package = isolated_paths
    selected = tmp_path / "historical-config"
    selected.mkdir()
    (selected / "preferences.json").write_text(
        '{"custom_setting": "keep-this-value"}', encoding="utf-8"
    )
    (package / "config_path").write_text(str(selected), encoding="utf-8")

    # update_config_path rebinds module globals; restore them after the test.
    for name in ("appdata_path", "preset_path", "backup_path"):
        monkeypatch.setattr(settings, name, getattr(settings, name))
    original_py_files_path = settings.standard_pref["py_files_path"]
    try:
        prefs = settings.get_preferences()
        assert prefs["custom_setting"] == "keep-this-value"
        assert settings.appdata_path == str(selected)
        assert settings.preset_path == str(selected / "Presets")
        assert settings.backup_path == str(selected / "Presets" / "Backup")
        assert (home / "config_path").read_text(encoding="utf-8") == str(selected)
    finally:
        settings.standard_pref["py_files_path"] = original_py_files_path


def test_first_run_still_uses_configuration_dialog(isolated_paths, tmp_path, monkeypatch):
    from nomad_camels.utility import load_save_functions as settings
    from nomad_camels.ui_widgets import path_button_edit

    home, package = isolated_paths
    selected = tmp_path / "new-custom-location"

    class FakeDirectoryDialog:
        def __init__(self, **kwargs):
            self.path = str(selected)

        def exec(self):
            return True

    monkeypatch.setattr(path_button_edit, "Path_Button_Dialog", FakeDirectoryDialog)
    for name in ("appdata_path", "preset_path", "backup_path"):
        monkeypatch.setattr(settings, name, getattr(settings, name))
    old_py_files = settings.standard_pref["py_files_path"]
    try:
        settings.check_config_path()
        assert settings.appdata_path == str(selected)
        assert selected.is_dir()
        assert (home / "config_path").read_text(encoding="utf-8") == str(selected)
        assert not (package / "config_path").exists()
    finally:
        settings.standard_pref["py_files_path"] = old_py_files
