"""Interface grafica (Flet) - operacoes por clique."""

import flet as ft

from ..container import Container, build_container
from ..domain.errors import PgCheckpointError, ValidationError
from ..domain.models import Checkpoint, DatabaseConfig


class CheckpointApp:
    def __init__(self, page: ft.Page, container: Container):
        self.page = page
        self.c = container
        self.busy = False

        # --- Controles principais ---
        self.db_dropdown = ft.Dropdown(
            label="Banco de dados",
            options=[],
            expand=True,
            on_select=lambda e: self.refresh_checkpoints(),
        )
        self.btn_register = ft.FilledButton(
            "Cadastrar banco",
            icon=ft.Icons.ADD,
            on_click=lambda e: self.open_register_dialog(),
        )
        self.btn_remove_db = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            tooltip="Remover banco selecionado (e seus checkpoints)",
            on_click=lambda e: self.confirm_remove_database(),
        )
        self.btn_refresh = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Atualizar listas",
            on_click=lambda e: self.refresh_all(),
        )

        self.checkpoint_name = ft.TextField(
            label="Nome do novo checkpoint",
            hint_text="ex: apos-setup-usuario",
            expand=True,
            on_submit=lambda e: self.save_checkpoint(),
        )
        self.btn_save = ft.FilledButton(
            "Salvar checkpoint",
            icon=ft.Icons.SAVE,
            on_click=lambda e: self.save_checkpoint(),
        )

        self.checkpoint_list = ft.ListView(expand=True, spacing=8)

        self.progress = ft.ProgressRing(width=18, height=18, visible=False)
        self.status = ft.Text("", size=13)

        page.add(
            ft.Column(
                expand=True,
                controls=[
                    ft.Text(
                        "PostgreSQL Checkpoint Manager",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Salve e restaure snapshots de bancos locais para testes.",
                        size=13,
                        color=ft.Colors.GREY,
                    ),
                    ft.Divider(),
                    ft.Row(
                        controls=[
                            self.db_dropdown,
                            self.btn_refresh,
                            self.btn_remove_db,
                            self.btn_register,
                        ]
                    ),
                    ft.Row(controls=[self.checkpoint_name, self.btn_save]),
                    ft.Divider(),
                    ft.Text("Checkpoints", size=16, weight=ft.FontWeight.BOLD),
                    self.checkpoint_list,
                    ft.Row(controls=[self.progress, self.status]),
                ],
            )
        )

        self.refresh_all()

    # --- Helpers ---

    def selected_db(self) -> DatabaseConfig | None:
        alias = self.db_dropdown.value
        if not alias:
            return None
        return self.c.database_service.get(alias)

    def notify(self, message: str, error: bool = False) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.RED_700 if error else ft.Colors.GREEN_700,
            )
        )
        self.page.update()

    def set_busy(self, busy: bool, status: str = "") -> None:
        self.busy = busy
        self.progress.visible = busy
        self.status.value = status
        for ctl in (
            self.btn_save,
            self.btn_register,
            self.btn_remove_db,
            self.btn_refresh,
            self.db_dropdown,
            self.checkpoint_name,
        ):
            ctl.disabled = busy
        self.page.update()

    # --- Atualizacao de listas ---

    def refresh_all(self) -> None:
        dbs = self.c.database_service.list()
        current = self.db_dropdown.value
        self.db_dropdown.options = [
            ft.DropdownOption(key=db.alias, text=db.display) for db in dbs
        ]
        aliases = [db.alias for db in dbs]
        if current in aliases:
            self.db_dropdown.value = current
        elif aliases:
            self.db_dropdown.value = aliases[0]
        else:
            self.db_dropdown.value = None
        self.refresh_checkpoints()

    def refresh_checkpoints(self) -> None:
        self.checkpoint_list.controls.clear()
        alias = self.db_dropdown.value
        if alias:
            checkpoints = self.c.checkpoint_service.list(alias)
            if not checkpoints:
                self.checkpoint_list.controls.append(
                    ft.Text("Nenhum checkpoint salvo para este banco.", color=ft.Colors.GREY)
                )
            for cp in checkpoints:
                self.checkpoint_list.controls.append(self._checkpoint_card(cp))
        else:
            self.checkpoint_list.controls.append(
                ft.Text(
                    "Nenhum banco cadastrado. Clique em 'Cadastrar banco' para comecar.",
                    color=ft.Colors.GREY,
                )
            )
        self.page.update()

    def _checkpoint_card(self, cp: Checkpoint) -> ft.Card:
        return ft.Card(
            content=ft.ListTile(
                leading=ft.Icon(ft.Icons.SAVE_OUTLINED),
                title=ft.Text(cp.name, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"{cp.created_at}  •  {cp.size_display}"),
                trailing=ft.Row(
                    width=100,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.RESTORE,
                            tooltip="Restaurar este checkpoint",
                            icon_color=ft.Colors.BLUE_400,
                            on_click=lambda e, cp=cp: self.confirm_restore(cp),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Remover este checkpoint",
                            icon_color=ft.Colors.RED_400,
                            on_click=lambda e, cp=cp: self.confirm_delete_checkpoint(cp),
                        ),
                    ],
                ),
            )
        )

    # --- Cadastrar banco ---

    def open_register_dialog(self) -> None:
        alias_f = ft.TextField(label="Nome/alias", hint_text="ex: meu-projeto-local")
        dbname_f = ft.TextField(label="Nome do banco (dbname)")
        port_f = ft.TextField(label="Porta", value="5432", width=120)
        user_f = ft.TextField(label="Usuario", value="postgres")
        password_f = ft.TextField(label="Senha", password=True, can_reveal_password=True)
        feedback = ft.Text("", size=12, color=ft.Colors.RED_400)
        testing = ft.ProgressRing(width=16, height=16, visible=False)

        def build_db() -> DatabaseConfig:
            alias = (alias_f.value or "").strip()
            self.c.database_service.validate_alias(alias)
            dbname = (dbname_f.value or "").strip()
            if not dbname:
                raise ValidationError("Nome do banco nao pode ser vazio.")
            port = self.c.database_service.validate_port((port_f.value or "").strip())
            return DatabaseConfig(
                alias=alias,
                dbname=dbname,
                port=port,
                user=(user_f.value or "postgres").strip() or "postgres",
                password=password_f.value or "",
            )

        def do_save(skip_test: bool = False) -> None:
            try:
                db = build_db()
            except ValidationError as err:
                feedback.value = str(err)
                self.page.update()
                return

            def work() -> None:
                if not skip_test:
                    testing.visible = True
                    feedback.value = "Testando conexao..."
                    feedback.color = ft.Colors.GREY
                    self.page.update()
                    ok, stderr = self.c.database_service.test_connection(db)
                    testing.visible = False
                    if not ok:
                        feedback.value = (
                            f"Falha na conexao: {stderr or 'erro desconhecido'}"
                        )
                        feedback.color = ft.Colors.RED_400
                        btn_force.visible = True
                        self.page.update()
                        return
                self.c.database_service.register(db)
                self.page.pop_dialog()
                self.refresh_all()
                self.db_dropdown.value = db.alias
                self.refresh_checkpoints()
                self.notify(f"Banco '{db.alias}' cadastrado com sucesso!")

            self.page.run_thread(work)

        btn_force = ft.TextButton(
            "Salvar mesmo assim",
            visible=False,
            on_click=lambda e: do_save(skip_test=True),
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Cadastrar banco de dados"),
            content=ft.Column(
                width=420,
                tight=True,
                controls=[
                    alias_f,
                    dbname_f,
                    ft.Row(controls=[port_f, user_f]),
                    password_f,
                    ft.Row(controls=[testing, feedback]),
                ],
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                btn_force,
                ft.FilledButton("Testar e salvar", on_click=lambda e: do_save()),
            ],
        )
        self.page.show_dialog(dialog)

    # --- Salvar checkpoint ---

    def save_checkpoint(self) -> None:
        if self.busy:
            return
        db = self.selected_db()
        if not db:
            self.notify("Cadastre/selecione um banco primeiro.", error=True)
            return

        name = (self.checkpoint_name.value or "").strip()
        try:
            self.c.checkpoint_service.validate_name(name)
        except ValidationError as e:
            self.notify(str(e), error=True)
            return

        if self.c.checkpoint_service.exists(db.alias, name):
            self._confirm(
                title="Sobrescrever checkpoint?",
                message=f"O checkpoint '{name}' ja existe. Sobrescrever?",
                action_label="Sobrescrever",
                on_confirm=lambda: self._do_save(db, name),
            )
        else:
            self._do_save(db, name)

    def _do_save(self, db: DatabaseConfig, name: str) -> None:
        def work() -> None:
            self.set_busy(True, f"Salvando checkpoint '{name}' de '{db.alias}'...")
            try:
                cp = self.c.checkpoint_service.save(db, name)
            except PgCheckpointError as e:
                self.set_busy(False)
                self.notify(str(e), error=True)
                return
            self.checkpoint_name.value = ""
            self.set_busy(False)
            self.refresh_checkpoints()
            self.notify(f"Checkpoint '{name}' salvo! ({cp.size_display})")

        self.page.run_thread(work)

    # --- Restaurar ---

    def confirm_restore(self, cp: Checkpoint) -> None:
        if self.busy:
            return
        db = self.selected_db()
        if not db:
            return
        self._confirm(
            title="Restaurar checkpoint?",
            message=(
                f"ATENCAO: isso vai APAGAR todos os dados atuais do banco "
                f"'{db.dbname}' e restaurar o checkpoint '{cp.name}' "
                f"({cp.created_at})."
            ),
            action_label="Restaurar",
            on_confirm=lambda: self._do_restore(db, cp),
            danger=True,
        )

    def _do_restore(self, db: DatabaseConfig, cp: Checkpoint) -> None:
        def progress(step: int, total: int, label: str) -> None:
            self.status.value = f"[{step}/{total}] {label}"
            self.page.update()

        def work() -> None:
            self.set_busy(True, f"Restaurando '{cp.name}' em '{db.dbname}'...")
            try:
                warning = self.c.checkpoint_service.restore(db, cp, progress)
            except PgCheckpointError as e:
                self.set_busy(False)
                self.notify(str(e), error=True)
                return
            self.set_busy(False)
            if warning:
                self.notify(f"Restaurado com aviso: {warning}")
            else:
                self.notify(f"Checkpoint '{cp.name}' restaurado com sucesso!")

        self.page.run_thread(work)

    # --- Remocoes ---

    def confirm_delete_checkpoint(self, cp: Checkpoint) -> None:
        if self.busy:
            return
        db = self.selected_db()
        if not db:
            return

        def do_delete() -> None:
            self.c.checkpoint_service.remove(db.alias, cp)
            self.refresh_checkpoints()
            self.notify(f"Checkpoint '{cp.name}' removido!")

        self._confirm(
            title="Remover checkpoint?",
            message=f"Remover o checkpoint '{cp.name}'? O arquivo de dump sera apagado.",
            action_label="Remover",
            on_confirm=do_delete,
            danger=True,
        )

    def confirm_remove_database(self) -> None:
        if self.busy:
            return
        db = self.selected_db()
        if not db:
            self.notify("Nenhum banco selecionado.", error=True)
            return

        def do_remove() -> None:
            self.c.database_service.remove(db.alias)
            self.refresh_all()
            self.notify(f"Banco '{db.alias}' removido!")

        self._confirm(
            title="Remover banco cadastrado?",
            message=(
                f"Isso vai remover o cadastro de '{db.alias}' e TODOS os seus "
                f"checkpoints salvos. (O banco PostgreSQL em si nao sera alterado.)"
            ),
            action_label="Remover",
            on_confirm=do_remove,
            danger=True,
        )

    # --- Dialogo de confirmacao generico ---

    def _confirm(
        self,
        title: str,
        message: str,
        action_label: str,
        on_confirm,
        danger: bool = False,
    ) -> None:
        def confirmed(e) -> None:
            self.page.pop_dialog()
            on_confirm()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton(
                    action_label,
                    bgcolor=ft.Colors.RED_700 if danger else None,
                    color=ft.Colors.WHITE if danger else None,
                    on_click=confirmed,
                ),
            ],
        )
        self.page.show_dialog(dialog)


def main(page: ft.Page) -> None:
    page.title = "PostgreSQL Checkpoint Manager"
    page.padding = 24
    try:
        page.window.width = 820
        page.window.height = 720
    except AttributeError:
        pass

    try:
        container = build_container()
    except PgCheckpointError as e:
        page.add(
            ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=48),
                    ft.Text("Erro ao iniciar", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(str(e), selectable=True),
                ]
            )
        )
        return

    CheckpointApp(page, container)


def run() -> None:
    ft.run(main)
