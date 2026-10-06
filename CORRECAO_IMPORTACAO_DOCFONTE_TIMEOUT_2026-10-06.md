# Correção do WORKER TIMEOUT no importador DocFonte — 2026-10-06

O log do Render mostrou `WORKER TIMEOUT` em `/payments/import-documents`. O XLSX do SIGFE possui 2.918 OS e a versão anterior fazia varreduras repetidas da lista completa de faturas para cada linha, além de manter todos os objetos SQLAlchemy pendentes até ao commit final.

## Correções
- Criados índices em memória por NIF, nome de fornecedor e número normalizado de factura.
- O cruzamento de cada OS deixou de percorrer todas as faturas.
- Importação em lotes de 200 OS por defeito (`CHIVUGEST_IMPORT_BATCH_SIZE`).
- Commit por lote e `expire_all()` para limitar o crescimento do identity map do SQLAlchemy.
- Mantida a leitura de até 100 colunas do DocFonte SIGFE.
- Mantido o mapeamento `Beneficiário`, `Nº OS`, `Situação OS`, `Valor Total MN`, `Finalidade da OS`, etc.
- Timeout do Gunicorn aumentado de 180 para 300 segundos como margem de segurança; a otimização é a correção principal.

## Validação
O DocFonte fornecido contém 3.173 linhas de dados e 2.918 linhas com Nº OS. A leitura XLSX foi validada com `openpyxl` em modo `read_only`.
