# Atualização da interface ChivuGest — 16/10/2026

## O que mudou
- Ecrã de login redesenhado com apresentação em dois painéis, identidade visual ChivuGest, descrição dos módulos e controlo para mostrar/ocultar palavra-passe.
- Área autenticada reorganizada com navegação lateral agrupada por área, realce da secção ativa, cabeçalho institucional, perfil do utilizador e rodapé.
- Logótipo e nome da instituição apresentados na área autenticada quando estão configurados em Configurações.
- Painel financeiro e componentes receberam ajustes visuais para legibilidade, hierarquia, tabelas e adaptação a ecrãs menores.
- Layout responsivo: navegação lateral compacta em tablets e barra inferior em telemóveis.
- Mantidos os nomes dos campos de autenticação e os destinos dos links existentes; esta atualização é principalmente visual e não substitui a validação das permissões no servidor.

## Validação
- `python -m py_compile app.py` concluído sem erros.
- Não foi possível executar o teste HTTP/visual nesta estação porque as dependências da aplicação (incluindo Flask) não estão instaladas no ambiente de validação.
- Antes de produção, validar login, menus por perfil, upload do logótipo, páginas de formulários e tabelas em desktop e telemóvel.
