# Correcao de arranque no Render — PostgreSQL (16/10/2026)

## Sintoma
O Render encerrava o processo durante `ensure_schema()` com:

`psycopg.errors.SyntaxError: syntax error at or near "user"`

na instrucao `ALTER TABLE user ADD COLUMN institution_id INTEGER`.

## Causa
`user` e uma palavra reservada no PostgreSQL. As migracoes SQL construidas manualmente nao delimitavam o nome da tabela.

## Correcao aplicada
- Delimitar os identificadores de tabela e coluna nas instrucoes `ALTER TABLE` e `UPDATE` geradas pela migracao.
- Delimitar explicitamente a tabela `user` nas atualizacoes dos perfis legados.
- Preservar a logica aditiva da migracao e os dados existentes.

## Validacao
- `app.py` passou na compilacao sintatica Python (`py_compile`).
- A inicializacao no Render e a migracao contra a base de dados de producao ainda precisam ser verificadas apos o deploy.

## Deploy
Publicar este pacote no repositorio ligado ao Render e aguardar os novos logs. Confirmar que a inicializacao termina sem erro SQL e que o servico abre a porta HTTP. Nao apagar nem recriar a base de dados para resolver este erro.
