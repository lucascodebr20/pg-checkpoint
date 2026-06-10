"""Erros do dominio, lancados pelos servicos e tratados pelas interfaces."""


class PgCheckpointError(Exception):
    """Base para erros esperados da aplicacao."""


class ValidationError(PgCheckpointError):
    pass


class PgToolsNotFoundError(PgCheckpointError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            f"Binarios do PostgreSQL nao encontrados: {', '.join(missing)}\n"
            "Verifique se o PostgreSQL esta instalado e adicione o diretorio 'bin' ao PATH.\n"
            "Locais verificados:\n"
            "  - PATH do sistema\n"
            "  - Windows: C:\\Program Files\\PostgreSQL\\<versao>\\bin\\\n"
            "  - macOS: /opt/homebrew/opt/postgresql@*/bin, Postgres.app\n"
            "  - Linux: /usr/lib/postgresql/<versao>/bin"
        )


class CommandTimeoutError(PgCheckpointError):
    def __init__(self, description: str):
        super().__init__(f"{description} excedeu o timeout de 1 hora.")


class CommandFailedError(PgCheckpointError):
    def __init__(self, description: str, stderr: str):
        self.stderr = stderr
        super().__init__(f"{description} falhou:\n{stderr.strip()}")
