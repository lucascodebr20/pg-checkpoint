"""Persistencia em disco: config.json e arquivos de dump/metadata."""

import json
import os
import shutil
from pathlib import Path

from ..domain.models import Checkpoint, DatabaseConfig
from ..settings import CONFIG_FILE, CONFIG_VERSION, DUMPS_DIR


class ConfigRepository:
    def __init__(self, config_file: Path = CONFIG_FILE):
        self._config_file = config_file

    def _load_raw(self) -> dict:
        if not self._config_file.exists():
            return {"version": CONFIG_VERSION, "databases": {}}
        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"version": CONFIG_VERSION, "databases": {}}

    def _save_raw(self, config: dict) -> None:
        tmp_file = self._config_file.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(str(tmp_file), str(self._config_file))

    def list_databases(self) -> list[DatabaseConfig]:
        raw = self._load_raw()
        return [
            DatabaseConfig.from_dict(alias, data)
            for alias, data in raw.get("databases", {}).items()
        ]

    def get(self, alias: str) -> DatabaseConfig | None:
        raw = self._load_raw()
        data = raw.get("databases", {}).get(alias)
        if data is None:
            return None
        return DatabaseConfig.from_dict(alias, data)

    def exists(self, alias: str) -> bool:
        return self.get(alias) is not None

    def upsert(self, db: DatabaseConfig) -> None:
        raw = self._load_raw()
        raw.setdefault("databases", {})[db.alias] = db.to_dict()
        self._save_raw(raw)

    def remove(self, alias: str) -> None:
        raw = self._load_raw()
        raw.get("databases", {}).pop(alias, None)
        self._save_raw(raw)


class CheckpointRepository:
    def __init__(self, dumps_dir: Path = DUMPS_DIR):
        self._dumps_dir = dumps_dir

    def dir_for(self, alias: str) -> Path:
        return self._dumps_dir / alias

    def ensure_dir(self, alias: str) -> Path:
        d = self.dir_for(alias)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def dump_path(self, alias: str, checkpoint: Checkpoint) -> Path:
        return self.dir_for(alias) / checkpoint.dump_file

    def list(self, alias: str) -> list[Checkpoint]:
        dump_dir = self.dir_for(alias)
        if not dump_dir.is_dir():
            return []

        checkpoints = []
        for meta_file in sorted(dump_dir.glob("*.meta")):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    checkpoints.append(Checkpoint.from_dict(json.load(f)))
            except (json.JSONDecodeError, OSError, KeyError):
                continue

        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints

    def exists(self, alias: str, name: str) -> bool:
        return (self.dir_for(alias) / f"{name}.dump").exists()

    def save_meta(self, checkpoint: Checkpoint) -> None:
        meta_file = self.dir_for(checkpoint.database_alias) / f"{checkpoint.name}.meta"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)

    def delete(self, alias: str, checkpoint: Checkpoint) -> None:
        dump_dir = self.dir_for(alias)
        dump_file = dump_dir / checkpoint.dump_file
        meta_file = dump_dir / f"{checkpoint.name}.meta"
        if dump_file.exists():
            dump_file.unlink()
        if meta_file.exists():
            meta_file.unlink()

    def delete_all(self, alias: str) -> None:
        dump_dir = self.dir_for(alias)
        if dump_dir.is_dir():
            shutil.rmtree(dump_dir)
