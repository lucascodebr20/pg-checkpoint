"""Casos de uso relacionados aos bancos cadastrados."""

from ..domain.errors import ValidationError
from ..domain.models import DatabaseConfig
from ..infrastructure.pg_commands import PgCommandRunner
from ..infrastructure.repositories import CheckpointRepository, ConfigRepository
from ..settings import ALIAS_PATTERN


class DatabaseService:
    def __init__(
        self,
        config_repo: ConfigRepository,
        checkpoint_repo: CheckpointRepository,
        runner: PgCommandRunner,
    ):
        self._config_repo = config_repo
        self._checkpoint_repo = checkpoint_repo
        self._runner = runner

    def list(self) -> list[DatabaseConfig]:
        return self._config_repo.list_databases()

    def get(self, alias: str) -> DatabaseConfig | None:
        return self._config_repo.get(alias)

    def exists(self, alias: str) -> bool:
        return self._config_repo.exists(alias)

    @staticmethod
    def validate_alias(alias: str) -> None:
        if not alias:
            raise ValidationError("Nome nao pode ser vazio.")
        if not ALIAS_PATTERN.match(alias):
            raise ValidationError("Use apenas letras, numeros, hifen e underscore.")

    @staticmethod
    def validate_port(port_str: str) -> int:
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
            return port
        except ValueError:
            raise ValidationError("Porta invalida.")

    def test_connection(self, db: DatabaseConfig) -> tuple[bool, str]:
        return self._runner.test_connection(db)

    def register(self, db: DatabaseConfig) -> None:
        self.validate_alias(db.alias)
        if not db.dbname:
            raise ValidationError("Nome do banco nao pode ser vazio.")
        self._config_repo.upsert(db)
        self._checkpoint_repo.ensure_dir(db.alias)

    def remove(self, alias: str) -> None:
        """Remove o cadastro e todos os checkpoints do banco."""
        self._config_repo.remove(alias)
        self._checkpoint_repo.delete_all(alias)
