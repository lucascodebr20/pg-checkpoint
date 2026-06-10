"""Entidades do dominio: banco cadastrado e checkpoint."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def format_size(bytes_count: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_count < 1024:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.1f} TB"


@dataclass(frozen=True)
class DatabaseConfig:
    alias: str
    dbname: str
    user: str
    password: str
    host: str = "localhost"
    port: int = 5432
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def display(self) -> str:
        return f"{self.alias}  ({self.user}@{self.host}:{self.port}/{self.dbname})"

    def to_dict(self) -> dict:
        return {
            "dbname": self.dbname,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, alias: str, data: dict) -> "DatabaseConfig":
        return cls(
            alias=alias,
            dbname=data["dbname"],
            host=data.get("host", "localhost"),
            port=int(data.get("port", 5432)),
            user=data.get("user", "postgres"),
            password=data.get("password", ""),
            registered_at=data.get("registered_at", ""),
        )


@dataclass(frozen=True)
class Checkpoint:
    name: str
    database_alias: str
    dbname: str
    created_at: str
    file_size_bytes: int
    dump_file: str

    @property
    def size_display(self) -> str:
        return format_size(self.file_size_bytes)

    @property
    def display(self) -> str:
        return f"{self.name}  ({self.created_at}, {self.size_display})"

    def to_dict(self) -> dict:
        return {
            "checkpoint_name": self.name,
            "database_alias": self.database_alias,
            "dbname": self.dbname,
            "created_at": self.created_at,
            "file_size_bytes": self.file_size_bytes,
            "dump_file": self.dump_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            name=data["checkpoint_name"],
            database_alias=data.get("database_alias", ""),
            dbname=data.get("dbname", ""),
            created_at=data.get("created_at", "?"),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            dump_file=data["dump_file"],
        )
