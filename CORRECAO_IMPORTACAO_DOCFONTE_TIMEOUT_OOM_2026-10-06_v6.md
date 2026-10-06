# Correção V6 — importação DocFonte SIGFE

- Remove consulta `PaymentOrder.query...first()` por linha.
- Duplicados passam a ser verificados em memória por `source_hash` do ficheiro.
- Fornecedores novos são criados em lote e recebem IDs via `flush()`.
- SourceDocument e PaymentOrder são inseridos com `bulk_insert_mappings()` em lotes.
- Mantida leitura XLSX em `read_only=True`.
- Dockerfile fixa Gunicorn com timeout de 300s e 1 worker.
- O formato SIGFE continua aceitando Beneficiário, Nº OS, Situação OS, Valor Total MN, Finalidade da OS e datas.
