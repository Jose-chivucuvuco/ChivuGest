# Correcção — eliminação segura de instituições e acesso global aos gestores

## Alterações
- Adicionada a acção **Eliminar** à lista de instituições, excepto para a instituição `DEFAULT` (Instituição Principal).
- A eliminação é recusada quando existirem registos operacionais/financeiros, contratos, pagamentos, documentos, importações, alertas ou backups associados. Nesses casos, a orientação é suspender a instituição para preservar o histórico.
- Quando a instituição não tem dados operacionais, os utilizadores e o perfil institucional associados são removidos; referências de auditoria são preservadas e desligadas da instituição/utilizadores eliminados.
- Corrigido o âmbito das consultas da Administração do Sistema a utilizadores: as listagens e operações globais ignoram explicitamente o filtro de isolamento por instituição, permitindo localizar e gerir os gestores recém-criados em qualquer instituição.
- Corrigida também a verificação global de nomes de utilizador duplicados na criação de instituição/gestor.
- Mantida a associação do Gestor institucional à instituição no acto de criação e a migração de geração automática do `institution_profile.id`.

## Validação e limites
- `app.py` compilado com `python -m py_compile`.
- O teste de integração Flask não pôde ser executado neste ambiente porque Flask/Flask-SQLAlchemy não estão instalados. A confirmação final do login, abertura do dashboard/perfil e eliminação deve ser feita num ambiente de teste antes do deploy de produção.
- Fazer backup do PostgreSQL antes de publicar.
