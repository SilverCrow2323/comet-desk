from __future__ import annotations

from pathlib import Path

from service import app_registry


def make_entry(root: Path, desktop_id: str, *, exec_line: str,
               name: str = "Demo App", extra: str = "") -> Path:
    binary = root / "usr" / "bin" / "demo-app"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    folder = root / "usr" / "share" / "applications"
    folder.mkdir(parents=True, exist_ok=True)
    entry = folder / desktop_id
    entry.write_text(
        "[Desktop Entry]\nType=Application\nName={}\nExec={}\nCategories=Utility;\n{}\n".format(
            name, exec_line, extra
        ),
        encoding="utf-8",
    )
    return entry


def test_parse_desktop_entry_resolves_binary_inside_rootfs(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    entry = make_entry(root, "demo.desktop", exec_line="demo-app %U")
    parsed = app_registry.parse_desktop_entry(entry, root)
    assert parsed is not None
    assert parsed["id"] == "demo"
    assert parsed["name"] == "Demo App"
    assert parsed["exec"][0] == "/usr/bin/demo-app"
    assert parsed["category"] == "UTILITIES"


def test_parse_desktop_entry_rejects_shell_and_external_executable(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    folder = root / "usr/share/applications"
    folder.mkdir(parents=True)
    shell = folder / "shell.desktop"
    shell.write_text("[Desktop Entry]\nType=Application\nName=Shell\nExec=sh -c 'id'\n")
    assert app_registry.parse_desktop_entry(shell, root) is None
    external = folder / "external.desktop"
    external.write_text("[Desktop Entry]\nType=Application\nName=External\nExec=/bin/echo\n")
    assert app_registry.parse_desktop_entry(external, root) is None


def test_parse_desktop_entry_skips_hidden_no_display_and_terminal_entries(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    hidden = make_entry(root, "hidden.desktop", exec_line="demo-app",
                        extra="Hidden=true")
    nodisplay = make_entry(root, "nodisplay.desktop", exec_line="demo-app",
                           extra="NoDisplay=true")
    terminal = make_entry(root, "terminal.desktop", exec_line="demo-app",
                          extra="Terminal=true")
    assert app_registry.parse_desktop_entry(hidden, root) is None
    assert app_registry.parse_desktop_entry(nodisplay, root) is None
    assert app_registry.parse_desktop_entry(terminal, root) is None


def test_catalog_discovery_is_stable_and_deduplicated(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    make_entry(root, "demo.desktop", exec_line="demo-app")
    make_entry(root, "other.desktop", exec_line="demo-app", name="Another Name")
    rows = app_registry.discover_applications(root)
    assert len(rows) == 2
    assert rows[0]["category"] == "UTILITIES"
    assert rows[0]["exec"] == ["/usr/bin/demo-app"]


def test_catalog_writer_uses_atomic_pipe_safe_rows(tmp_path):
    app_registry.write_catalog(tmp_path, [{
        "id": "demo.app",
        "name": "Demo | App",
        "category": "UTILITIES",
        "icon": "application-x-executable",
        "exec": ["/usr/bin/demo-app"],
    }])
    path = tmp_path / "data" / "app-catalog.txt"
    assert path.read_text().splitlines() == [
        "META|1",
        "APP|demo.app|Demo / App|UTILITIES|application-x-executable|/usr/bin/demo-app",
    ]
    assert not path.with_suffix(".tmp").exists()


def test_application_ids_are_validated_before_lookup(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    try:
        app_registry.find_application(root, "../../etc/passwd")
    except app_registry.RegistryError:
        pass
    else:
        raise AssertionError("invalid application id was accepted")


def test_parse_desktop_entry_rejects_command_and_privilege_wrappers(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    folder = root / "usr/share/applications"
    folder.mkdir(parents=True)
    wrapper = folder / "wrapper.desktop"
    wrapper.write_text(
        "[Desktop Entry]\nType=Application\nName=Wrapper\n"
        "Exec=/usr/bin/env demo-app\n",
        encoding="utf-8",
    )
    assert app_registry.parse_desktop_entry(wrapper, root) is None
