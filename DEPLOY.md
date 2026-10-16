# ChivuGest Online — publicação

Esta versão é preparada para vários utilizadores simultâneos e usa PostgreSQL quando `DATABASE_URL` é fornecida.

## Opção simples: Render
1. Crie um repositório GitHub e envie todos os ficheiros desta pasta.
2. No Render, crie um serviço Web a partir do repositório.
3. Use:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn --bind 0.0.0.0:$PORT app:app`
4. Crie uma base PostgreSQL e configure `DATABASE_URL`.
5. Configure `SECRET_KEY` com um valor aleatório.
6. O serviço terá um endereço HTTPS que poderá partilhar com os funcionários.

## Primeiro acesso
Não use credenciais padrão. Configure `SYSTEM_ADMIN_USERNAME` e `SYSTEM_ADMIN_PASSWORD` (mínimo de 12 caracteres) para criar o Administrador do Sistema. Para uma instalação nova, configure também `INITIAL_ADMIN_PASSWORD` (mínimo de 10 caracteres) para criar o Gestor da instituição principal. Guarde as credenciais no gestor de segredos do alojamento.

## OCR
PDF digital pode ser lido com PyMuPDF. PDF escaneado depende do Tesseract OCR no servidor. Em serviços cloud, o Tesseract deve ser instalado no ambiente de execução e os idiomas `por`/`eng` devem estar disponíveis.

## Dados
Não use SQLite para vários computadores em produção. Use PostgreSQL através de `DATABASE_URL`.


## Parâmetros legais e actualização automática

Para activar a verificação automática das fontes legais:
- `AUTO_LEGAL_CHECK=true`
- `LEGAL_CHECK_INTERVAL_HOURS=6`

A verificação consulta as fontes configuradas, regista o hash do conteúdo e cria um histórico. Se houver alteração, o estado fica como **Alteração detectada — validação necessária**. O ChivuGest não altera automaticamente limites ou regras jurídicas a partir de texto não validado.

A opção manual **Verificar actualizações agora** está disponível em **Base legal** para administradores.

## Nota sobre actualização da base de dados

A versão usa `db.create_all()` e as novas tabelas legais são aditivas. Não devem ser apagadas as bases de dados existentes durante a actualização.


## Multi-instituição
Defina SYSTEM_ADMIN_USERNAME e SYSTEM_ADMIN_PASSWORD no gestor de segredos para provisionar o Administrador do Sistema. Para uma instalação nova, defina também INITIAL_ADMIN_PASSWORD para o utilizador admin da instituição principal. Não use credenciais padrão. Na primeira inicialização a migração aditiva associa os registos antigos à instituição DEFAULT. Em PostgreSQL, a migração também substitui as restrições globais de código de Acordo-Quadro, procedimento e contrato por restrições por instituição. Faça backup e teste o isolamento entre instituições antes da produção. Em bases SQLite antigas, as restrições UNIQUE antigas exigem migração específica antes de permitir códigos repetidos entre instituições.
