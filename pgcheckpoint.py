#!/usr/bin/env python3
"""PostgreSQL Checkpoint Manager - save and restore database snapshots for local testing."""

import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# === Constants ===
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR / ".pgcheckpoint"
CONFIG_FILE = BASE_DIR / "config.json"
DUMPS_DIR = BASE_DIR / "dumps"
ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
CONFIG_VERSION = 1
SUBPROCESS_TIMEOUT = 3600  # 1 hour


# === UI Helpers ===


def print_header(text: str) -> None:
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print(f"{'=' * 50}\n")


def print_error(text: str) -> None:
    print(f"\n  [ERRO] {text}\n")


def print_success(text: str) -> None:
    print(f"\n  [OK] {text}\n")


def print_warning(text: str) -> None:
    print(f"\n  [AVISO] {text}\n")


def prompt_choice(prompt_text: str, options: list[str]) -> int:
    """Show numbered list and return selected index (0-based), or -1 if cancelled."""
    if not options:
        print_error("Nenhuma opcao disponivel.")
        return -1

    print()
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  0. Voltar")
    print()

    while True:
        raw = input(prompt_text).strip()
        if raw == "0":
            return -1
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return idx - 1
        except ValueError:
            pass
        print_error(f"Opcao invalida. Digite um numero de 0 a {len(options)}.")


def prompt_yn(prompt_text: str, default: bool = False) -> bool:
    suffix = " [S/n]: " if default else " [s/N]: "
    raw = input(prompt_text + suffix).strip().lower()
    if raw == "":
        return default
    return raw in ("s", "sim", "y", "yes")


def format_size(bytes_count: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_count < 1024:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.1f} TB"


# === Binary Discovery ===

_pg_binary_cache: dict[str, str] = {}


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
    # Homebrew versioned
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
    # Homebrew general
    dirs.append(Path("/opt/homebrew/bin"))
    dirs.append(Path("/usr/local/bin"))
    # Postgres.app
    dirs.append(
        Path("/Applications/Postgres.app/Contents/Versions/latest/bin")
    )
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
    if name in _pg_binary_cache:
        return _pg_binary_cache[name]

    # 1. Try PATH
    found = shutil.which(name)
    if found:
        _pg_binary_cache[name] = found
        return found

    # 2. Platform-specific search
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
            _pg_binary_cache[name] = result
            return result

    return None


def ensure_pg_tools() -> dict[str, str]:
    tools = {}
    missing = []
    for name in ("pg_dump", "pg_restore", "psql"):
        path = find_pg_binary(name)
        if path:
            tools[name] = path
        else:
            missing.append(name)

    if missing:
        print_error(
            f"Binarios do PostgreSQL nao encontrados: {', '.join(missing)}\n"
            f"  Verifique se o PostgreSQL esta instalado e adicione o diretorio 'bin' ao PATH.\n"
            f"  Locais verificados:\n"
            f"    - PATH do sistema\n"
            f"    - Windows: C:\\Program Files\\PostgreSQL\\<versao>\\bin\\\n"
            f"    - macOS: /opt/homebrew/opt/postgresql@*/bin, Postgres.app\n"
            f"    - Linux: /usr/lib/postgresql/<versao>/bin"
        )
        sys.exit(1)

    return tools


# === Config Management ===


def ensure_dirs() -> None:
    BASE_DIR.mkdir(exist_ok=True)
    DUMPS_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"version": CONFIG_VERSION, "databases": {}}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print_warning(f"Erro ao ler config.json: {e}")
        print_warning("Criando configuracao nova.")
        return {"version": CONFIG_VERSION, "databases": {}}


def save_config(config: dict) -> None:
    tmp_file = CONFIG_FILE.with_suffix(".json.tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.replace(str(tmp_file), str(CONFIG_FILE))


# === Subprocess Helper ===


def run_pg_command(
    cmd: list[str], password: str, description: str
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    try:
        return subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print_error(f"{description} excedeu o timeout de 1 hora.")
        raise SystemExit(1)
    except FileNotFoundError:
        print_error(f"Binario nao encontrado: {cmd[0]}")
        raise SystemExit(1)


# === Core Operations ===


def select_database(config: dict) -> str | None:
    """Show database list and return selected alias, or None."""
    dbs = config.get("databases", {})
    if not dbs:
        print_error("Nenhum banco de dados cadastrado. Use a opcao 1 primeiro.")
        return None

    options = []
    aliases = []
    for alias, info in dbs.items():
        options.append(
            f"{alias}  ({info['user']}@localhost:{info['port']}/{info['dbname']})"
        )
        aliases.append(alias)

    idx = prompt_choice("Selecione o banco: ", options)
    if idx < 0:
        return None
    return aliases[idx]


def select_checkpoint(alias: str) -> dict | None:
    """Show checkpoint list for a database and return metadata dict, or None."""
    dump_dir = DUMPS_DIR / alias
    if not dump_dir.is_dir():
        print_error(f"Nenhum checkpoint encontrado para '{alias}'.")
        return None

    metas = []
    for meta_file in sorted(dump_dir.glob("*.meta")):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                metas.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue

    if not metas:
        print_error(f"Nenhum checkpoint encontrado para '{alias}'.")
        return None

    metas.sort(key=lambda m: m.get("created_at", ""), reverse=True)

    options = []
    for m in metas:
        size = format_size(m.get("file_size_bytes", 0))
        created = m.get("created_at", "?")
        options.append(f"{m['checkpoint_name']}  ({created}, {size})")

    idx = prompt_choice("Selecione o checkpoint: ", options)
    if idx < 0:
        return None
    return metas[idx]


def register_database(config: dict, tools: dict[str, str]) -> None:
    print_header("Cadastrar Banco de Dados")

    # Alias
    while True:
        alias = input("  Nome/alias (ex: meu-projeto-local): ").strip()
        if not alias:
            print_error("Nome nao pode ser vazio.")
            continue
        if not ALIAS_PATTERN.match(alias):
            print_error("Use apenas letras, numeros, hifen e underscore.")
            continue
        if alias in config.get("databases", {}):
            if not prompt_yn(f"  '{alias}' ja existe. Sobrescrever?"):
                continue
        break

    # Connection details
    dbname = input("  Nome do banco (dbname): ").strip()
    if not dbname:
        print_error("Nome do banco nao pode ser vazio.")
        return

    host = "localhost"

    port_str = input("  Porta [5432]: ").strip() or "5432"
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        print_error("Porta invalida.")
        return

    user = input("  Usuario [postgres]: ").strip() or "postgres"
    password = getpass.getpass("  Senha: ")

    # Test connection
    print("\n  Testando conexao...")
    result = run_pg_command(
        [tools["psql"], "-h", host, "-p", str(port), "-U", user, "-d", dbname, "-c", "SELECT 1;"],
        password,
        "teste de conexao",
    )

    if result.returncode != 0:
        print_error(f"Falha na conexao:\n{result.stderr.strip()}")
        if not prompt_yn("  Salvar mesmo assim?"):
            return

    # Save
    config.setdefault("databases", {})[alias] = {
        "dbname": dbname,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    save_config(config)

    # Create dumps directory
    (DUMPS_DIR / alias).mkdir(exist_ok=True)

    print_success(f"Banco '{alias}' cadastrado com sucesso!")


def save_checkpoint(config: dict, tools: dict[str, str]) -> None:
    print_header("Salvar Checkpoint")

    alias = select_database(config)
    if not alias:
        return

    db = config["databases"][alias]
    dump_dir = DUMPS_DIR / alias
    dump_dir.mkdir(exist_ok=True)

    # Checkpoint name
    while True:
        name = input("  Nome do checkpoint (ex: apos-setup-usuario): ").strip()
        if not name:
            print_error("Nome nao pode ser vazio.")
            continue
        if not ALIAS_PATTERN.match(name):
            print_error("Use apenas letras, numeros, hifen e underscore.")
            continue
        dump_file = dump_dir / f"{name}.dump"
        if dump_file.exists():
            if not prompt_yn(f"  Checkpoint '{name}' ja existe. Sobrescrever?"):
                continue
        break

    meta_file = dump_dir / f"{name}.meta"

    print(f"\n  Salvando checkpoint '{name}' do banco '{alias}'...")
    print(f"  ({db['user']}@{db['host']}:{db['port']}/{db['dbname']})")
    print()

    cmd = [
        tools["pg_dump"],
        "-Fc",
        "--no-owner",
        "--no-acl",
        "-h", db["host"],
        "-p", str(db["port"]),
        "-U", db["user"],
        "-d", db["dbname"],
        "-f", str(dump_file),
    ]

    result = run_pg_command(cmd, db["password"], "pg_dump")

    if result.returncode != 0:
        print_error(f"pg_dump falhou:\n{result.stderr.strip()}")
        # Clean up partial file
        if dump_file.exists():
            dump_file.unlink()
        return

    # Write metadata
    file_size = dump_file.stat().st_size
    meta = {
        "checkpoint_name": name,
        "database_alias": alias,
        "dbname": db["dbname"],
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "file_size_bytes": file_size,
        "dump_file": f"{name}.dump",
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print_success(f"Checkpoint '{name}' salvo! ({format_size(file_size)})")


def drop_database_with_retry(
    tools: dict[str, str], db: dict, max_retries: int = 3
) -> bool:
    psql = tools["psql"]
    host, port, user, password = db["host"], str(db["port"]), db["user"], db["password"]
    dbname = db["dbname"]
    safe_dbname = dbname.replace("'", "''")

    for attempt in range(max_retries):
        # Terminate connections
        terminate_sql = (
            f"SELECT pg_terminate_backend(pid) "
            f"FROM pg_stat_activity "
            f"WHERE datname = '{safe_dbname}' "
            f"AND pid <> pg_backend_pid();"
        )
        run_pg_command(
            [psql, "-h", host, "-p", port, "-U", user, "-d", "postgres", "-c", terminate_sql],
            password,
            "terminar conexoes",
        )

        # Drop database
        drop_sql = f'DROP DATABASE IF EXISTS "{dbname}";'
        result = run_pg_command(
            [psql, "-h", host, "-p", port, "-U", user, "-d", "postgres", "-c", drop_sql],
            password,
            "drop database",
        )

        if result.returncode == 0:
            return True

        if "being accessed by other users" in result.stderr and attempt < max_retries - 1:
            print(f"  Banco ainda tem conexoes ativas, tentando novamente ({attempt + 1}/{max_retries})...")
            time.sleep(1)
            continue

        print_error(f"Falha ao remover banco:\n{result.stderr.strip()}")
        return False

    print_error("Nao foi possivel remover o banco apos multiplas tentativas.")
    return False


def restore_checkpoint(config: dict, tools: dict[str, str]) -> None:
    print_header("Restaurar Checkpoint")

    alias = select_database(config)
    if not alias:
        return

    db = config["databases"][alias]
    meta = select_checkpoint(alias)
    if not meta:
        return

    dump_file = DUMPS_DIR / alias / meta["dump_file"]
    if not dump_file.exists():
        print_error(f"Arquivo de dump nao encontrado: {dump_file}")
        return

    print(f"\n  Banco: {db['dbname']} ({db['user']}@{db['host']}:{db['port']})")
    print(f"  Checkpoint: {meta['checkpoint_name']} ({meta['created_at']})")
    print()
    print("  ATENCAO: Isso vai APAGAR todos os dados atuais do banco")
    print(f"  '{db['dbname']}' e restaurar o checkpoint '{meta['checkpoint_name']}'.")
    print()

    if not prompt_yn("  Continuar?"):
        return

    # Step 1: Drop database
    print("\n  [1/3] Removendo banco atual...")
    if not drop_database_with_retry(tools, db):
        return

    # Step 2: Create fresh database
    print("  [2/3] Criando banco novo...")
    create_sql = f'CREATE DATABASE "{db["dbname"]}";'
    result = run_pg_command(
        [
            tools["psql"], "-h", db["host"], "-p", str(db["port"]),
            "-U", db["user"], "-d", "postgres", "-c", create_sql,
        ],
        db["password"],
        "create database",
    )
    if result.returncode != 0:
        print_error(f"Falha ao criar banco:\n{result.stderr.strip()}")
        return

    # Step 3: Restore
    print("  [3/3] Restaurando checkpoint...")
    cmd = [
        tools["pg_restore"],
        "--no-owner",
        "--no-acl",
        "-h", db["host"],
        "-p", str(db["port"]),
        "-U", db["user"],
        "-d", db["dbname"],
        str(dump_file),
    ]
    result = run_pg_command(cmd, db["password"], "pg_restore")

    # pg_restore returns 1 for warnings (missing roles, etc.) - that's usually OK
    if result.returncode > 1:
        print_error(f"pg_restore falhou:\n{result.stderr.strip()}")
        return

    if result.returncode == 1:
        stderr = result.stderr.strip()
        if "FATAL" in stderr or "could not connect" in stderr:
            print_error(f"pg_restore falhou:\n{stderr}")
            return
        print_warning("pg_restore completou com avisos (geralmente inofensivos).")

    # Verify
    verify = run_pg_command(
        [
            tools["psql"], "-h", db["host"], "-p", str(db["port"]),
            "-U", db["user"], "-d", db["dbname"], "-c", "SELECT 1;",
        ],
        db["password"],
        "verificacao",
    )
    if verify.returncode == 0:
        print_success(
            f"Checkpoint '{meta['checkpoint_name']}' restaurado com sucesso!"
        )
    else:
        print_warning(
            "Restauracao concluida, mas a verificacao falhou. "
            "O banco pode estar em estado incompleto."
        )


def list_checkpoints(config: dict) -> None:
    print_header("Checkpoints Salvos")

    dbs = config.get("databases", {})
    if not dbs:
        print_error("Nenhum banco cadastrado.")
        return

    found_any = False

    for alias in sorted(dbs.keys()):
        db = dbs[alias]
        dump_dir = DUMPS_DIR / alias
        if not dump_dir.is_dir():
            continue

        metas = []
        for meta_file in sorted(dump_dir.glob("*.meta")):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    metas.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue

        if not metas:
            continue

        found_any = True
        print(f"  {alias}  ({db['user']}@localhost:{db['port']}/{db['dbname']})")
        print(f"  {'─' * 46}")

        metas.sort(key=lambda m: m.get("created_at", ""))
        for m in metas:
            size = format_size(m.get("file_size_bytes", 0))
            created = m.get("created_at", "?")
            print(f"    {m['checkpoint_name']:<30} {created}  {size}")
        print()

    if not found_any:
        print("  Nenhum checkpoint salvo ainda.")
        print()


def remove_entry(config: dict, tools: dict[str, str]) -> None:
    print_header("Remover")

    print("  1. Remover um banco de dados cadastrado")
    print("  2. Remover um checkpoint")
    print("  0. Voltar")
    print()

    choice = input("Selecione: ").strip()

    if choice == "1":
        alias = select_database(config)
        if not alias:
            return

        print(f"\n  Isso vai remover o cadastro de '{alias}' e todos os seus checkpoints.")
        if not prompt_yn("  Continuar?"):
            return

        del config["databases"][alias]
        save_config(config)

        dump_dir = DUMPS_DIR / alias
        if dump_dir.is_dir():
            shutil.rmtree(dump_dir)

        print_success(f"Banco '{alias}' removido!")

    elif choice == "2":
        alias = select_database(config)
        if not alias:
            return

        meta = select_checkpoint(alias)
        if not meta:
            return

        if not prompt_yn(f"  Remover checkpoint '{meta['checkpoint_name']}'?"):
            return

        dump_dir = DUMPS_DIR / alias
        dump_file = dump_dir / meta["dump_file"]
        meta_file = dump_dir / f"{meta['checkpoint_name']}.meta"

        if dump_file.exists():
            dump_file.unlink()
        if meta_file.exists():
            meta_file.unlink()

        print_success(f"Checkpoint '{meta['checkpoint_name']}' removido!")


# === Main ===


def main() -> None:
    try:
        ensure_dirs()
        tools = ensure_pg_tools()
        config = load_config()

        while True:
            print_header("PostgreSQL Checkpoint Manager")
            print("  1. Cadastrar banco de dados")
            print("  2. Salvar checkpoint (pg_dump)")
            print("  3. Restaurar checkpoint (pg_restore)")
            print("  4. Listar checkpoints")
            print("  5. Remover banco/checkpoint")
            print("  0. Sair")
            print()

            choice = input("Selecione uma opcao: ").strip()

            if choice == "1":
                register_database(config, tools)
            elif choice == "2":
                save_checkpoint(config, tools)
            elif choice == "3":
                restore_checkpoint(config, tools)
            elif choice == "4":
                list_checkpoints(config)
            elif choice == "5":
                remove_entry(config, tools)
            elif choice == "0":
                print("\n  Ate mais!\n")
                break
            else:
                print_error("Opcao invalida.")

    except KeyboardInterrupt:
        print("\n\n  Ate mais!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
