# ChivuGest — Multi-instituição e perfis de acesso

## Modelo de acesso
- `system_admin`: administra a plataforma e cria/suspende instituições; não entra nos módulos financeiros por defeito.
- `institution_admin`: gere utilizadores e dados apenas da instituição associada.
- `technician`: consulta e regista, sem editar/eliminar registos existentes.
- `auditor`: apenas leitura.

## Isolamento de dados
As tabelas operacionais recebem `institution_id`. A migração atribui os registos preexistentes à instituição `DEFAULT`, sem os apagar. As consultas ORM são filtradas pela instituição autenticada e as gravações validam propriedade e relações entre registos. Dados legais de referência são globais; alertas de conformidade e auditoria operacional são isolados por instituição.

## Primeiro Administrador do Sistema
Por segurança, não existe palavra-passe padrão para o administrador global. Configure no ambiente de execução:
- `SYSTEM_ADMIN_USERNAME`
- `SYSTEM_ADMIN_PASSWORD` (mínimo de 12 caracteres)

O sistema cria essa conta no arranque se ainda não existir. Para uma instalação nova, configure também `INITIAL_ADMIN_PASSWORD` para a conta `admin` da instituição principal. Não reutilize palavras-passe entre ambientes.

## Migração e publicação
1. Fazer backup integral da base de dados.
2. Instalar a versão e iniciar a aplicação para executar a migração aditiva.
3. Verificar que os dados legados pertencem à instituição `DEFAULT`.
4. Configurar as credenciais de Administrador do Sistema no gestor de segredos do alojamento.
5. Criar novas instituições no menu **Instituições** e atribuir o Gestor inicial.
6. Executar testes de isolamento entre duas instituições antes de usar dados reais.

## Limitações e validação pendente
A migração e as proteções são implementadas no código da aplicação, mas devem ser validadas com a base de dados real e testes de segurança. Para produção de alto risco, recomenda-se complementar o isolamento ORM com Row-Level Security na base de dados e testes automatizados de tentativas de acesso cruzado. As operações de backup/restauro devem ser revistas para garantir que um gestor institucional não restaura dados globais ou de outra instituição.
