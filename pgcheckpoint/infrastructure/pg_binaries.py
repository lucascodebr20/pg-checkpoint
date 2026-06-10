"""Descoberta dos binarios do PostgreSQL (pg_dump, pg_restore, psql) no sistema."""

import platform
import shutil
from pathlib import Path

from ..domain.errors import PgToolsNotFoundError

_cache: dict[str, str] = {}


def _windows_pg_dirs() -> list[Path]:
    dirs = []
    base = Path(r"C:\Program Files\PostgreSQL")
    if base.is_dir():
        versions = sorted(
            [d for d in base.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        for v in versions:
            bin_dir = v / "bin"
            if bin_dir.is_dir():
                dirs.append(bin_dir)
    return dirs


def _macos_pg_dirs() -> list[Path]:
    dirs = []
    # Homebrew com versao
    for base in (Path("/opt/homebrew/opt"), Path("/usr/local/opt")):
        if base.is_dir():
            pg_dirs = sorted(
                [d for d in base.iterdir() if d.name.startswith("postgresql@")],
                key=lambda d: d.name,
                reverse=True,
            )
            for d in pg_dirs:
                bin_dir = d / "bin"
                if bin_dir.is_dir():
                    dirs.append(bin_dir)
    # Homebrew geral
    dirs.append(Path("/opt/homebrew/bin"))
    dirs.append(Path("/usr/local/bin"))
    # Postgres.app
    dirs.append(Path("/Applications/Postgres.app/Contents/Versions/latest/bin"))
    return dirs


def _linux_pg_dirs() -> list[Path]:
    dirs = []
    pg_base = Path("/usr/lib/postgresql")
    if pg_base.is_dir():
        versions = sorted(
            [d for d in pg_base.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        for v in versions:
            bin_dir = v / "bin"
            if bin_dir.is_dir():
                dirs.append(bin_dir)
    dirs.append(Path("/usr/bin"))
    dirs.append(Path("/usr/local/bin"))
    return dirs


def find_pg_binary(name: str) -> str | None:
    if name in _cache:
        return _cache[name]

    found = shutil.which(name)
    if found:
        _cache[name] = found
        return found

    system = platform.system()
    search_name = name
    if system == "Windows" and not name.endswith(".exe"):
        search_name = name + ".exe"

    if system == "Windows":
        search_dirs = _windows_pg_dirs()
    elif system == "Darwin":
        search_dirs = _macos_pg_dirs()
    else:
        search_dirs = _linux_pg_dirs()

    for d in search_dirs:
        candidate = d / search_name
        if candidate.is_file():
            result = str(candidate)
            _cache[name] = result
            return result

    return None


def ensure_pg_tools() -> dict[str, str]:
    """Retorna {nome: caminho} dos binarios ou lanca PgToolsNotFoundError."""
    tools = {}
    missing = []
    for name in ("pg_dump", "pg_restore", "psql"):
        path = find_pg_binary(name)
        if path:
            tools[name] = path
        else:
            missing.append(name)

    if missing:
        raise PgToolsNotFoundError(missing)

    return tools
