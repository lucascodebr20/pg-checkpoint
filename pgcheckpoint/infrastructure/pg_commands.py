"""Execucao dos comandos pg_dump / pg_restore / psql via subprocess."""

import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from ..domain.errors import CommandFailedError, CommandTimeoutError
from ..domain.models import DatabaseConfig
from ..settings import SUBPROCESS_TIMEOUT


class PgCommandRunner:
    def __init__(self, tools: dict[str, str]):
        self._tools = tools

    def _run(
        self, cmd: list[str], password: str, description: str
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
            raise CommandTimeoutError(description)
        except FileNotFoundError:
            raise CommandFailedError(description, f"Binario nao encontrado: {cmd[0]}")

    def _psql(
        self, db: DatabaseConfig, sql: str, description: str, dbname: str | None = None
    ) -> subprocess.CompletedProcess:
        return self._run(
            [
                self._tools["psql"],
                "-h", db.host,
                "-p", str(db.port),
                "-U", db.user,
                "-d", dbname or db.dbname,
                "-c", sql,
            ],
            db.password,
            description,
        )

    def test_connection(self, db: DatabaseConfig) -> tuple[bool, str]:
        """Retorna (sucesso, stderr)."""
        result = self._psql(db, "SELECT 1;", "teste de conexao")
        return result.returncode == 0, result.stderr.strip()

    def dump(self, db: DatabaseConfig, dump_file: Path) -> None:
        cmd = [
            self._tools["pg_dump"],
            "-Fc",
            "--no-owner",
            "--no-acl",
            "-h", db.host,
            "-p", str(db.port),
            "-U", db.user,
            "-d", db.dbname,
            "-f", str(dump_file),
        ]
        result = self._run(cmd, db.password, "pg_dump")
        if result.returncode != 0:
            if dump_file.exists():
                dump_file.unlink()
            raise CommandFailedError("pg_dump", result.stderr)

    def drop_database(
        self,
        db: DatabaseConfig,
        max_retries: int = 3,
        on_retry: Callable[[int, int], None] | None = None,
    ) -> None:
        safe_dbname = db.dbname.replace("'", "''")
        for attempt in range(max_retries):
            terminate_sql = (
                f"SELECT pg_terminate_backend(pid) "
                f"FROM pg_stat_activity "
                f"WHERE datname = '{safe_dbname}' "
                f"AND pid <> pg_backend_pid();"
            )
            self._psql(db, terminate_sql, "terminar conexoes", dbname="postgres")

            drop_sql = f'DROP DATABASE IF EXISTS "{db.dbname}";'
            result = self._psql(db, drop_sql, "drop database", dbname="postgres")

            if result.returncode == 0:
                return

            if (
                "being accessed by other users" in result.stderr
                and attempt < max_retries - 1
            ):
                if on_retry:
                    on_retry(attempt + 1, max_retries)
                time.sleep(1)
                continue

            raise CommandFailedError("Remocao do banco", result.stderr)

        raise CommandFailedError(
            "Remocao do banco",
            "Nao foi possivel remover o banco apos multiplas tentativas.",
        )

    def create_database(self, db: DatabaseConfig) -> None:
        create_sql = f'CREATE DATABASE "{db.dbname}";'
        result = self._psql(db, create_sql, "create database", dbname="postgres")
        if result.returncode != 0:
            raise CommandFailedError("Criacao do banco", result.stderr)

    def restore(self, db: DatabaseConfig, dump_file: Path) -> str | None:
        """Restaura o dump. Retorna mensagem de aviso (ou None se limpo)."""
        cmd = [
            self._tools["pg_restore"],
            "--no-owner",
            "--no-acl",
            "-h", db.host,
            "-p", str(db.port),
            "-U", db.user,
            "-d", db.dbname,
            str(dump_file),
        ]
        result = self._run(cmd, db.password, "pg_restore")

        # pg_restore retorna 1 para avisos (roles ausentes etc.) - geralmente OK
        if result.returncode > 1:
            raise CommandFailedError("pg_restore", result.stderr)

        if result.returncode == 1:
            stderr = result.stderr.strip()
            if "FATAL" in stderr or "could not connect" in stderr:
                raise CommandFailedError("pg_restore", stderr)
            return "pg_restore completou com avisos (geralmente inofensivos)."

        return None
