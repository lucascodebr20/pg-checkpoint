"""Interface de linha de comando (menu interativo)."""

import getpass
import sys

from ..container import Container, build_container
from ..domain.errors import PgCheckpointError, ValidationError
from ..domain.models import Checkpoint, DatabaseConfig


# === Helpers de exibicao ===


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
    """Mostra lista numerada e retorna indice selecionado (0-based), ou -1 para voltar."""
    if not options:
        print_error("Nenhuma opcao disponivel.")
        return -1

    print()
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  0. Voltar")
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


# === Selecao ===


def select_database(c: Container) -> DatabaseConfig | None:
    dbs = c.database_service.list()
    if not dbs:
        print_error("Nenhum banco de dados cadastrado. Use a opcao 1 primeiro.")
        return None

    idx = prompt_choice("Selecione o banco: ", [db.display for db in dbs])
    if idx < 0:
        return None
    return dbs[idx]


def select_checkpoint(c: Container, alias: str) -> Checkpoint | None:
    checkpoints = c.checkpoint_service.list(alias)
    if not checkpoints:
        print_error(f"Nenhum checkpoint encontrado para '{alias}'.")
        return None

    idx = prompt_choice("Selecione o checkpoint: ", [cp.display for cp in checkpoints])
    if idx < 0:
        return None
    return checkpoints[idx]


# === Fluxos ===


def register_database(c: Container) -> None:
    print_header("Cadastrar Banco de Dados")

    while True:
        alias = input("  Nome/alias (ex: meu-projeto-local): ").strip()
        try:
            c.database_service.validate_alias(alias)
        except ValidationError as e:
            print_error(str(e))
            continue
        if c.database_service.exists(alias):
            if not prompt_yn(f"  '{alias}' ja existe. Sobrescrever?"):
                continue
        break

    dbname = input("  Nome do banco (dbname): ").strip()
    if not dbname:
        print_error("Nome do banco nao pode ser vazio.")
        return

    port_str = input("  Porta [5432]: ").strip() or "5432"
    try:
        port = c.database_service.validate_port(port_str)
    except ValidationError as e:
        print_error(str(e))
        return

    user = input("  Usuario [postgres]: ").strip() or "postgres"
    password = getpass.getpass("  Senha: ")

    db = DatabaseConfig(
        alias=alias, dbname=dbname, port=port, user=user, password=password
    )

    print("\n  Testando conexao...")
    ok, stderr = c.database_service.test_connection(db)
    if not ok:
        print_error(f"Falha na conexao:\n{stderr}")
        if not prompt_yn("  Salvar mesmo assim?"):
            return

    c.database_service.register(db)
    print_success(f"Banco '{alias}' cadastrado com sucesso!")


def save_checkpoint(c: Container) -> None:
    print_header("Salvar Checkpoint")

    db = select_database(c)
    if not db:
        return

    while True:
        name = input("  Nome do checkpoint (ex: apos-setup-usuario): ").strip()
        try:
            c.checkpoint_service.validate_name(name)
        except ValidationError as e:
            print_error(str(e))
            continue
        if c.checkpoint_service.exists(db.alias, name):
            if not prompt_yn(f"  Checkpoint '{name}' ja existe. Sobrescrever?"):
                continue
        break

    print(f"\n  Salvando checkpoint '{name}' do banco '{db.alias}'...")
    print(f"  ({db.user}@{db.host}:{db.port}/{db.dbname})")
    print()

    try:
        checkpoint = c.checkpoint_service.save(db, name)
    except PgCheckpointError as e:
        print_error(str(e))
        return

    print_success(f"Checkpoint '{name}' salvo! ({checkpoint.size_display})")


def restore_checkpoint(c: Container) -> None:
    print_header("Restaurar Checkpoint")

    db = select_database(c)
    if not db:
        return

    checkpoint = select_checkpoint(c, db.alias)
    if not checkpoint:
        return

    print(f"\n  Banco: {db.dbname} ({db.user}@{db.host}:{db.port})")
    print(f"  Checkpoint: {checkpoint.name} ({checkpoint.created_at})")
    print()
    print("  ATENCAO: Isso vai APAGAR todos os dados atuais do banco")
    print(f"  '{db.dbname}' e restaurar o checkpoint '{checkpoint.name}'.")
    print()

    if not prompt_yn("  Continuar?"):
        return

    def progress(step: int, total: int, label: str) -> None:
        print(f"  [{step}/{total}] {label}")

    print()
    try:
        warning = c.checkpoint_service.restore(db, checkpoint, progress)
    except PgCheckpointError as e:
        print_error(str(e))
        return

    if warning:
        print_warning(warning)
    print_success(f"Checkpoint '{checkpoint.name}' restaurado com sucesso!")


def list_checkpoints(c: Container) -> None:
    print_header("Checkpoints Salvos")

    dbs = c.database_service.list()
    if not dbs:
        print_error("Nenhum banco cadastrado.")
        return

    found_any = False
    for db in sorted(dbs, key=lambda d: d.alias):
        checkpoints = c.checkpoint_service.list(db.alias)
        if not checkpoints:
            continue

        found_any = True
        print(f"  {db.display}")
        print(f"  {'─' * 46}")
        for cp in sorted(checkpoints, key=lambda x: x.created_at):
            print(f"    {cp.name:<30} {cp.created_at}  {cp.size_display}")
        print()

    if not found_any:
        print("  Nenhum checkpoint salvo ainda.")
        print()


def remove_entry(c: Container) -> None:
    print_header("Remover")

    print("  1. Remover um banco de dados cadastrado")
    print("  2. Remover um checkpoint")
    print("  0. Voltar")
    print()

    choice = input("Selecione: ").strip()

    if choice == "1":
        db = select_database(c)
        if not db:
            return

        print(f"\n  Isso vai remover o cadastro de '{db.alias}' e todos os seus checkpoints.")
        if not prompt_yn("  Continuar?"):
            return

        c.database_service.remove(db.alias)
        print_success(f"Banco '{db.alias}' removido!")

    elif choice == "2":
        db = select_database(c)
        if not db:
            return

        checkpoint = select_checkpoint(c, db.alias)
        if not checkpoint:
            return

        if not prompt_yn(f"  Remover checkpoint '{checkpoint.name}'?"):
            return

        c.checkpoint_service.remove(db.alias, checkpoint)
        print_success(f"Checkpoint '{checkpoint.name}' removido!")


# === Loop principal ===


def run() -> None:
    try:
        try:
            c = build_container()
        except PgCheckpointError as e:
            print_error(str(e))
            sys.exit(1)

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
                register_database(c)
            elif choice == "2":
                save_checkpoint(c)
            elif choice == "3":
                restore_checkpoint(c)
            elif choice == "4":
                list_checkpoints(c)
            elif choice == "5":
                remove_entry(c)
            elif choice == "0":
                print("\n  Ate mais!\n")
                break
            else:
                print_error("Opcao invalida.")

    except KeyboardInterrupt:
        print("\n\n  Ate mais!\n")
        sys.exit(0)
