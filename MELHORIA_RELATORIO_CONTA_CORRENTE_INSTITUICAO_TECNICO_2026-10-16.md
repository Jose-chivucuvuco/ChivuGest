# Melhoria do relatório de conta corrente — 16/10/2026

## Alterações
- Criado perfil institucional configurável, persistido na tabela `institution_profile` (criada pelo `db.create_all()` existente).
- Em Configurações, o administrador pode editar nome oficial, órgão de tutela, NIF, morada, telefone, e-mail e logótipo PNG/JPG.
- O relatório PDF de conta corrente apresenta cabeçalho institucional, logótipo quando configurado, dados do fornecedor, técnico responsável, data de emissão e resumo financeiro com estilo profissional.
- O técnico responsável é obtido do nome do utilizador autenticado (`User.name`). Para manter essa identificação correta, o administrador deve cadastrar cada técnico com o nome completo na área Utilizadores.
- Na listagem de relatórios, a ação Visualizar abre o PDF no navegador; Descarregar PDF mantém o download.
- A rota PDF aceita `preview=1` para apresentação inline, sem mudar o comportamento de download padrão.

## Validação
- `python -m py_compile app.py` executado sem erros.
- Teste funcional de geração PDF não executado neste ambiente, pois a dependência Flask não está instalada. Deve ser validado na aplicação de testes antes de publicar.
