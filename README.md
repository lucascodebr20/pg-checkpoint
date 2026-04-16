# pg-savestate

Ferramenta CLI para salvar e restaurar snapshots de bancos PostgreSQL locais, agilizando testes em ambiente de desenvolvimento.

> **⚠️ Aviso: Este projeto foi feito exclusivamente para uso em ambiente local de desenvolvimento. Não utilize em produção ou com dados reais. Os dumps gerados pelo pg_dump não possuem criptografia, qualquer pessoa com acesso ao arquivo pode ler todo o conteúdo do banco. Credenciais também são armazenadas em texto plano no disco.**

## O problema

Durante testes locais, frequentemente precisamos preparar o banco de dados (criar usuários, popular tabelas, chegar em determinado estado) antes de testar uma funcionalidade. Esse processo manual e repetitivo consome tempo.

## A solução

O pg-savestate funciona como um sistema de **checkpoints**: salva o estado atual do banco e restaura depois, pulando todo o setup manual.

```
=== PostgreSQL Checkpoint Manager ===
  1. Cadastrar banco de dados
  2. Salvar checkpoint (pg_dump)
  3. Restaurar checkpoint (pg_restore)
  4. Listar checkpoints
  5. Remover banco/checkpoint
  0. Sair
```

## Requisitos

- Python 3.10+
- PostgreSQL (pg_dump, pg_restore, psql)

## Como usar

**Windows:** duplo clique no `pgcheckpoint.bat`

**Mac/Linux:** duplo clique no `pgcheckpoint.sh` ou:

```bash
./pgcheckpoint.sh
```

Ou diretamente com Python:

```bash
python pgcheckpoint.py
```

### Fluxo básico

1. **Cadastre o banco** informando nome do banco, porta, usuário e senha.
2. **Salve um checkpoint** escolhendo o banco e dando um nome ao checkpoint (ex: `apos-setup-usuario`).
3. **Faça seus testes** e altere os dados à vontade.
4. **Restaure o checkpoint** para voltar ao estado salvo instantaneamente.

## Compatibilidade

- Windows
- macOS
- Linux

O script detecta automaticamente os binários do PostgreSQL no sistema.

## Estrutura dos dados

Os dados ficam em `.pgcheckpoint/` ao lado do script (já incluído no `.gitignore`):

```
.pgcheckpoint/
  config.json              # conexões cadastradas
  dumps/
    <alias>/
      <checkpoint>.dump    # snapshot do banco (pg_dump)
      <checkpoint>.meta    # metadata (data, tamanho)
```
