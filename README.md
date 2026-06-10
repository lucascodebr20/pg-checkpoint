# pg-savestate

Ferramenta para salvar e restaurar snapshots de bancos PostgreSQL locais, agilizando testes em ambiente de desenvolvimento. Disponível em duas interfaces: **gráfica (GUI)** e **terminal (CLI)**.

> Toda a aplicação foi desenvolvida usando o **Claude Code** (modelo **Fable**).

> **⚠️ Aviso: Este projeto foi feito exclusivamente para uso em ambiente local de desenvolvimento. Não utilize em produção ou com dados reais. Os dumps gerados pelo pg_dump não possuem criptografia, qualquer pessoa com acesso ao arquivo pode ler todo o conteúdo do banco. Credenciais também são armazenadas em texto plano no disco.**

## O problema

Durante testes locais, frequentemente precisamos preparar o banco de dados (criar usuários, popular tabelas, chegar em determinado estado) antes de testar uma funcionalidade. Esse processo manual e repetitivo consome tempo.

## A solução

O pg-savestate funciona como um sistema de **checkpoints**: salva o estado atual do banco e restaura depois, pulando todo o setup manual.

## Requisitos

- Python 3.10+
- PostgreSQL (pg_dump, pg_restore, psql)
- [Flet](https://flet.dev) para a interface gráfica:

```bash
pip install -r requirements.txt
```

## Como usar

### Interface gráfica (recomendado)

**Windows:** duplo clique no `pgcheckpoint.bat` (abre só a janela da aplicação, sem terminal)

**Mac/Linux:** `./pgcheckpoint.sh`

Ou diretamente:

```bash
python -m pgcheckpoint
```

Na janela é possível cadastrar bancos, salvar checkpoints, restaurar e remover — tudo por clique, com confirmação antes de operações destrutivas.

> Se o Flet não estiver instalado, a aplicação abre automaticamente no modo terminal.

### Modo terminal

```bash
python -m pgcheckpoint --cli
```

```
=== PostgreSQL Checkpoint Manager ===
  1. Cadastrar banco de dados
  2. Salvar checkpoint (pg_dump)
  3. Restaurar checkpoint (pg_restore)
  4. Listar checkpoints
  5. Remover banco/checkpoint
  0. Sair
```

### Fluxo básico

1. **Cadastre o banco** informando nome do banco, porta, usuário e senha.
2. **Salve um checkpoint** escolhendo o banco e dando um nome ao checkpoint (ex: `apos-setup-usuario`).
3. **Faça seus testes** e altere os dados à vontade.
4. **Restaure o checkpoint** para voltar ao estado salvo instantaneamente.

## Arquitetura

O código é organizado em camadas, com dependências apontando sempre para dentro (UI → serviços → infraestrutura → domínio):

```
pgcheckpoint/
  __main__.py                # entry point (GUI por padrão, --cli para terminal)
  settings.py                # caminhos e constantes
  container.py               # montagem das dependências (composition root)
  domain/                    # entidades e erros (sem dependências externas)
    models.py                # DatabaseConfig, Checkpoint
    errors.py                # hierarquia de erros da aplicação
  infrastructure/            # acesso a recursos externos
    pg_binaries.py           # descoberta dos binários do PostgreSQL
    pg_commands.py           # execução de pg_dump/pg_restore/psql
    repositories.py          # persistência (config.json, dumps, metadata)
  services/                  # regras de negócio (casos de uso)
    database_service.py      # cadastrar/listar/remover bancos
    checkpoint_service.py    # salvar/restaurar/listar/remover checkpoints
  ui/                        # camada de apresentação
    cli.py                   # menu interativo no terminal
    gui.py                   # interface gráfica (Flet)
```

As interfaces (CLI e GUI) usam os mesmos serviços — qualquer nova funcionalidade fica disponível para ambas.

## Compatibilidade

- Windows
- macOS
- Linux

O script detecta automaticamente os binários do PostgreSQL no sistema.

## Estrutura dos dados

Os dados ficam em `.pgcheckpoint/` na raiz do projeto (já incluído no `.gitignore`):

```
.pgcheckpoint/
  config.json              # conexões cadastradas
  dumps/
    <alias>/
      <checkpoint>.dump    # snapshot do banco (pg_dump)
      <checkpoint>.meta    # metadata (data, tamanho)
```
