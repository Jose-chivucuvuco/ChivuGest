# Correção Render — SIGKILL / Internal Server Error — 2026-10-06

## Causa identificada
O worker Gunicorn estava a executar `run_compliance_checks()` durante a inicialização da aplicação e também em páginas GET como Dashboard, Alertas e Relatórios. Essa rotina percorre acordos, contratos, faturas e procedimentos e executa vários agregados/consultas por registo. Em bases de dados de produção, isso pode consumir memória suficiente para o Render enviar SIGKILL ao worker.

## Correções
1. Removida a execução completa de `run_compliance_checks()` durante `init_db()`.
2. Removida a execução automática em GET do Dashboard.
3. Removida a execução automática em GET de Alertas.
4. Removida a execução automática em GET de Relatórios.
5. Mantida a execução após operações de criação/alteração onde já existia, para preservar a atualização da conformidade após mudanças de dados.
6. Mantida a correção do importador DocFonte SIGFE: leitura até 100 colunas, reconhecimento de Beneficiário/Nº OS/Situação OS/valores MN/finalidade e tratamento de datas.

## Deploy no Render
Usar o ZIP desta versão e fazer novo deploy. Não é necessário alterar o `DATABASE_URL`.

Depois do deploy, testar primeiro:
- `/health` → deve responder `OK`;
- login;
- Dashboard;
- Importar o DocFonte XLSX.

A rotina de conformidade deixa de bloquear o arranque do servidor.
