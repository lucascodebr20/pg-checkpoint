"""Casos de uso relacionados aos checkpoints (salvar, restaurar, listar, remover)."""

from datetime import datetime, timezone
from typing import Callable

from ..domain.errors import CommandFailedError, ValidationError
from ..domain.models import Checkpoint, DatabaseConfig
from ..infrastructure.pg_commands import PgCommandRunner
from ..infrastructure.repositories import CheckpointRepository
from ..settings import ALIAS_PATTERN

ProgressCallback = Callable[[int, int, str], None]


class CheckpointService:
    def __init__(self, checkpoint_repo: CheckpointRepository, runner: PgCommandRunner):
        self._repo = checkpoint_repo
        self._runner = runner

    def list(self, alias: str) -> list[Checkpoint]:
        return self._repo.list(alias)

    def exists(self, alias: str, name: str) -> bool:
        return self._repo.exists(alias, name)

    @staticmethod
    def validate_name(name: str) -> None:
        if not name:
            raise ValidationError("Nome nao pode ser vazio.")
        if not ALIAS_PATTERN.match(name):
            raise ValidationError("Use apenas letras, numeros, hifen e underscore.")

    def save(self, db: DatabaseConfig, name: str) -> Checkpoint:
        self.validate_name(name)
        dump_dir = self._repo.ensure_dir(db.alias)
        dump_file = dump_dir / f"{name}.dump"

        self._runner.dump(db, dump_file)

        checkpoint = Checkpoint(
            name=name,
            database_alias=db.alias,
            dbname=db.dbname,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            file_size_bytes=dump_file.stat().st_size,
            dump_file=f"{name}.dump",
        )
        self._repo.save_meta(checkpoint)
        return checkpoint

    def restore(
        self,
        db: DatabaseConfig,
        checkpoint: Checkpoint,
        progress: ProgressCallback | None = None,
    ) -> str | None:
        """Restaura um checkpoint (drop + create + restore + verificacao).

        Retorna mensagem de aviso, ou None se tudo limpo.
        Lanca CommandFailedError em falhas.
        """
        dump_file = self._repo.dump_path(db.alias, checkpoint)
        if not dump_file.exists():
            raise CommandFailedError(
                "Restauracao", f"Arquivo de dump nao encontrado: {dump_file}"
            )

        def report(step: int, label: str) -> None:
            if progress:
                progress(step, 3, label)

        report(1, "Removendo banco atual...")
        self._runner.drop_database(db)

        report(2, "Criando banco novo...")
        self._runner.create_database(db)

        report(3, "Restaurando checkpoint...")
        warning = self._runner.restore(db, dump_file)

        ok, _ = self._runner.test_connection(db)
        if not ok:
            return (
                "Restauracao concluida, mas a verificacao falhou. "
                "O banco pode estar em estado incompleto."
            )
        return warning

    def remove(self, alias: str, checkpoint: Checkpoint) -> None:
        self._repo.delete(alias, checkpoint)
