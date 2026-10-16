# Importação do Livro de Ordem de Saque — 16/10/2026

- `Nº Doc` → número da Ordem de Saque (`os_number`).
- `Situação` → estado da OS, preservando estados como `Paga` e `Cancelada`.
- `Data` → data da OS.
- `Valor` → valor monetário da OS.
- `Beneficiário` → identificação do fornecedor, necessária para cruzamento com as faturas e para evitar duplicados por fornecedor.
- `Finalidade` → campo auxiliar para localizar/reconciliar faturas; não substitui o número oficial da fatura nem gera pagamento isoladamente.
- A importação não cria um pagamento bancário efetivo; cria/regista a OS operacional e o respetivo documento de origem conforme o fluxo existente.
- A mesma OS para o mesmo fornecedor é ignorada quando já existe.
- PDF de Livro de OS com texto pesquisável é interpretado por linha; linhas seguintes de descrição são anexadas apenas à `Finalidade`. PDFs digitalizados podem necessitar OCR e devem ser validados.
