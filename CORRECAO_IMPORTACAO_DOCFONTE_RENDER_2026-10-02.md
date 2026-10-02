# Correção — Importação DocFonte / Livro de Ordens de Saque

## Problema observado
A rota `/payments/import-documents` sofria `WORKER TIMEOUT` no Render ao importar ficheiros XLSX grandes. O log mostrava o worker do Gunicorn a expirar durante `normalize_key`, chamado pela leitura do workbook.

## Correções aplicadas
- Leitura XLSX em modo streaming (`read_only=True`) sem materializar o workbook inteiro em memória.
- Limite configurável de linhas: `CHIVUGEST_IMPORT_MAX_ROWS` (padrão 5.000).
- Limite configurável de colunas: `CHIVUGEST_IMPORT_MAX_COLUMNS` (padrão 40).
- Detecção do cabeçalho nas primeiras linhas, permitindo títulos/linhas vazias antes do cabeçalho.
- Leitura CSV também limitada e em streaming.
- O ficheiro é lido uma única vez e o hash é calculado uma única vez.
- Removida a chamada repetida a `f.getvalue()` dentro do ciclo.
- Fornecedores e faturas são carregados uma vez por lote para evitar consultas N+1.
- Cache de reconciliação para linhas repetidas.
- Atualização do cache quando um novo fornecedor é criado durante o lote.
- Normalização adicional para cabeçalhos como `Nº da OS`, `Nº OS`, `Número da OS`, `Nº da Fatura`, `Valor OS`, `Data OS`, `Situação OS`.

## Proteção do Render
O `render.yaml` continua configurado com um único worker e timeout de 180 segundos. A otimização reduz o trabalho síncrono para que a importação normal termine antes do timeout padrão de serviços que ainda estejam configurados com 30 segundos.

Se o serviço Render existente não estiver a usar o `render.yaml`, o Start Command deve ser atualizado para:

`gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 180 --max-requests 20 --max-requests-jitter 5 app:app`

## Resultado esperado
Ao importar o Livro de Ordens de Saque/DocFonte XLSX:
- não deve carregar todo o histórico em memória;
- não deve executar consultas completas de fornecedores/faturas para cada linha;
- não deve provocar o `WORKER TIMEOUT` observado no log;
- a importação mantém o cruzamento por fornecedor, NIF, fatura, valor e situação;
- a OS continua a ser apenas reconciliada e não convertida automaticamente em pagamento efetivado.
