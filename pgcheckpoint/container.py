"""Montagem das dependencias da aplicacao (composition root)."""

from dataclasses import dataclass

from .infrastructure.pg_binaries import ensure_pg_tools
from .infrastructure.pg_commands import PgCommandRunner
from .infrastructure.repositories import CheckpointRepository, ConfigRepository
from .services.checkpoint_service import CheckpointService
from .services.database_service import DatabaseService
from .settings import ensure_dirs


@dataclass(frozen=True)
class Container:
    database_service: DatabaseService
    checkpoint_service: CheckpointService


def build_container() -> Container:
    """Cria as dependencias. Lanca PgToolsNotFoundError se faltar binario."""
    ensure_dirs()
    tools = ensure_pg_tools()
    runner = PgCommandRunner(tools)
    config_repo = ConfigRepository()
    checkpoint_repo = CheckpointRepository()
    return Container(
        database_service=DatabaseService(config_repo, checkpoint_repo, runner),
        checkpoint_service=CheckpointService(checkpoint_repo, runner),
    )
