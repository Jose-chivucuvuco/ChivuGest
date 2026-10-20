ChivuGest — Correcção de isolamento multi-instituição v6
Data: 2026-10-20

Alterações em v12/app.py:
- O login procura a conta globalmente antes de definir o contexto institucional.
- login_required verifica se institution_id na sessão corresponde à instituição atribuída ao utilizador.
- O filtro ORM de isolamento falha de forma fechada quando uma requisição não tem contexto institucional: não devolve dados operacionais de todas as instituições.
- Operações administrativas globais devem usar skip_tenant_scope=True apenas nas consultas específicas que realmente precisam de âmbito global.

Importante:
- Todas as instituições continuam a usar a mesma base de dados física; os registos são separados por institution_id e filtros de consulta.
- Validar em ambiente de teste com duas instituições e contas distintas antes de produção.
- Fazer backup da base de dados antes da publicação. Não é necessária migração destrutiva.
