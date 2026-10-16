# Checklist de validação antes de produção

A compilação sintática e a validação de templates não substituem testes funcionais com a base de dados real. Executar este roteiro num ambiente de teste após fazer backup.

1. Configurar `SYSTEM_ADMIN_USERNAME` e `SYSTEM_ADMIN_PASSWORD`; iniciar sessão como Administrador do Sistema.
2. Criar Instituição A e Instituição B, cada uma com o seu Gestor institucional.
3. Em A, criar fornecedor, fatura, contrato, pagamento e documento fonte. Repetir em B com os mesmos nomes e números quando aplicável.
4. Confirmar que Gestor A não consegue pesquisar, abrir, editar, eliminar, associar ou exportar os registos de B, mesmo ao alterar manualmente IDs na URL ou formulário.
5. Confirmar que Técnico A só vê os módulos operacionais autorizados, consegue registar informação nova e não consegue editar/eliminar registos existentes.
6. Confirmar que Auditor A só consulta relatórios, conta corrente, análise e base legal; todos os POST de alteração são recusados.
7. Confirmar que Gestor A não consegue criar utilizador Administrador do Sistema nem alterar o próprio `role` ou `institution_id` através da administração genérica.
8. Repetir a importação do mesmo ficheiro em A: deve detetar duplicado. Importar o mesmo ficheiro em B: deve ser permitido e permanecer isolado de A.
9. Confirmar que os relatórios PDF mostram a identificação e o logótipo de cada instituição, sem mistura de fornecedores ou pagamentos.
10. Confirmar que apenas Administrador do Sistema pode criar/suspender instituições e gerar/restaurar backup global.
11. Testar a migração numa cópia de PostgreSQL existente, verificar contagens antes/depois e confirmar que os registos antigos pertencem à instituição `DEFAULT`.
12. Não publicar até todos os testes passarem e a equipa validar as políticas de retenção, auditoria e recuperação.

## Limitações conhecidas
- A base SQLite preexistente pode manter restrições UNIQUE globais antigas nos códigos de Acordo-Quadro, procedimento e contrato; antes de repetir esses códigos entre instituições, fazer a migração específica indicada em `DEPLOY.md`.
- O isolamento é implementado no ORM e nas validações de gravação. Para ambientes com exigência elevada, acrescentar Row-Level Security em PostgreSQL e testes automatizados de segurança.
