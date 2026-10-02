# ChivuGest — Melhorias do módulo de Relatórios — 02/10/2026

## Implementado

1. Painel de Relatórios com indicadores de Faturado, Pago, A Pagar, Fornecedores, Acordos-Quadro, Contratos e Alertas.
2. Filtros por fornecedor, Acordo-Quadro, contrato, estado e período.
3. Tabela consolidada por fornecedor com faturado, pago, saldo, número de faturas, alertas e documentos.
4. PDF individual formatado por fornecedor.
5. PDF consolidado de fornecedores.
6. ZIP com um PDF individual para cada fornecedor.
7. Importação de PDF associada diretamente a um fornecedor, com tipo documental, hash anti-duplicação, OCR/extracção e armazenamento do ficheiro.
8. Download posterior dos PDFs importados.
9. Exportação CSV com `csv.writer`, preservando nomes de fornecedores que contenham vírgulas.
10. Recuperação compatível com o CSV legado que tinha vírgulas nos nomes e colunas numéricas deslocadas; o saldo é recalculado como Total - Pago.
11. Migração aditiva da tabela `source_document` para guardar invoice/contract/framework e conteúdo PDF, sem apagar dados existentes.
12. Dependência `reportlab` adicionada para geração de PDFs no ambiente de produção.

## Regras de consistência

- O relatório usa `SupplierInvoice.total` e `SupplierInvoice.paid` para manter os totais da tela, CSV e PDF consistentes.
- O estado `Vencida` é calculado quando existe saldo e a data de vencimento é anterior à data atual.
- O PDF individual mantém o NIF e o nome completo do fornecedor.
- A exportação CSV utiliza campos corretamente delimitados/quotados.

- Exportações de relatório agora incluem a coluna **Ordem de Saque (N.º)**, agregando todas as OS vinculadas à fatura.
- PDFs individuais de fornecedor também exibem o número da Ordem de Saque associado a cada fatura.
- A tela de relatórios apresenta a contagem de Ordens de Saque por fornecedor.
