CORREÇÃO — PostgreSQL institution_profile.id
Data: 2026-10-19

Problema observado nos logs:
ERROR: null value in column "id" of relation "institution_profile" violates not-null constraint

Alteração:
- Em ensure_schema(), quando o motor é PostgreSQL e a tabela existe, cria (se necessário) uma sequência para institution_profile.id.
- Define a sequência como pertencente à coluna e como DEFAULT de id.
- Alinha o próximo valor ao maior ID existente, para preservar registos e evitar colisões.
- A operação é idempotente; não apaga nem recria a tabela ou os dados.

Validação realizada:
- Sintaxe Python compilada com sucesso.
- ZIP reconstruído e testado quanto à integridade.

Limitação:
- Não foi possível testar contra a base de dados privada do Render nesta sessão. Fazer backup antes do deploy e confirmar os logs depois da publicação.
