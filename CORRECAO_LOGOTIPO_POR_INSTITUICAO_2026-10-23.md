# Correcção — logótipo por instituição (23/10/2026)

Consolidada na versão actual do ChivuGest, preservando as funcionalidades existentes.

- O cabeçalho utiliza uma rota dedicada para obter o logótipo da instituição autenticada.
- A rota valida a instituição da sessão (excepto Administrador do Sistema), limita o ficheiro à pasta `static/uploads` e devolve cabeçalhos de cache privados e sem armazenamento.
- A URL inclui a data de actualização do perfil para evitar reutilização de imagem antiga.

Validar em ambiente de teste com pelo menos duas instituições e contas distintas antes da publicação em produção.
