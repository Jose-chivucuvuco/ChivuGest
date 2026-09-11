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
Utilizador: `admin`
Senha: `admin123`

Altere a palavra-passe inicial antes de colocar o sistema em produção. A versão atual já cria utilizadores, mas recomenda-se acrescentar uma página específica de alteração de palavra-passe antes de uso empresarial definitivo.

## OCR
PDF digital pode ser lido com PyMuPDF. PDF escaneado depende do Tesseract OCR no servidor. Em serviços cloud, o Tesseract deve ser instalado no ambiente de execução e os idiomas `por`/`eng` devem estar disponíveis.

## Dados
Não use SQLite para vários computadores em produção. Use PostgreSQL através de `DATABASE_URL`.
