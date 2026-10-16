
# Correção de permissões: Administrador do Sistema, instituição e utilizadores

## Criar o Administrador do Sistema no Render

Em Render > serviço ChivuGest > Environment, configurar `SYSTEM_ADMIN_USERNAME` e `SYSTEM_ADMIN_PASSWORD` (mínimo 12 caracteres) como variáveis secretas e fazer deploy/restart. A criação ocorre no arranque apenas se ainda não existir utilizador com esse username. Se esse username já existir com outro perfil, use um username único ou faça a promoção de forma controlada na base de dados, com backup prévio. Não partilhe credenciais por chat.

## Alterações desta versão

- O Administrador do Sistema pode editar a identificação institucional a partir de Instituições > Editar identificação (nome, NIF, tutela, contactos e logótipo).
- O Gestor institucional pode eliminar utilizadores da sua própria instituição, exceto a própria conta, Administradores do Sistema ou outros Gestores institucionais. Utilizadores com registos relacionados podem não ser elimináveis; nesse caso, desative a conta para bloquear o acesso.
- A ação Ativar/Desativar passou para POST e é verificada no servidor.
- As operações são limitadas pela instituição da sessão e registadas em auditoria.

Validar em staging com duas instituições e utilizadores de teste antes de produção. A eliminação física depende das relações existentes na base de dados; quando houver dependências, a aplicação deve recusar a eliminação e sugerir desativação.
