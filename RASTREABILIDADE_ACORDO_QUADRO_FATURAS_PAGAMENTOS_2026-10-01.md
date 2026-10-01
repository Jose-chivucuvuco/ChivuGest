# ChivuGest — Rastreabilidade Acordo-Quadro → Contrato → Fatura → Pagamento

## Alterações
- `SupplierInvoice` ganhou `framework_agreement_id`.
- `SupplierPayment` ganhou `framework_agreement_id`.
- `PaymentOrder` ganhou `framework_agreement_id`.
- Ao registar uma fatura, o contrato é a fonte de verdade quando selecionado; o Acordo-Quadro é herdado automaticamente do contrato.
- Uma fatura pode ser ligada diretamente a um Acordo-Quadro quando ainda não existe contrato.
- Ao registar um pagamento com fatura, fornecedor, contrato e Acordo-Quadro são herdados automaticamente da fatura.
- Ao registar um pagamento com contrato, o fornecedor e o Acordo-Quadro são herdados do contrato.
- Validações impedem combinações inconsistentes entre fornecedor, Acordo-Quadro e contrato.
- Ordens de saque importadas passam a guardar o Acordo-Quadro correspondente quando este pode ser identificado pela fatura/contrato.
- A interface de Faturas e Pagamentos apresenta Acordo-Quadro e Contrato separadamente.
- Filtros dependentes mostram apenas Acordos-Quadro/contratos compatíveis com o fornecedor.
- A migração preenche o novo campo em registos existentes quando já havia contrato associado.

## Fluxo
Fornecedor → Acordo-Quadro → Contrato → Fatura → Pagamento

O Acordo-Quadro continua independente do contrato: pode existir com zero contratos associados.
