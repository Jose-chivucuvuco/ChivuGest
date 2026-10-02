# Correções — Importação inteligente / OCR — 02-10-2026

## Fatura de teste: ROCHA MONTEIRO, LDA — Fatura 1971

O parser foi ajustado para reconhecer corretamente documentos com OCR semelhante ao documento de teste.

### Campos esperados no documento
- Fornecedor: ROCHA MONTEIRO, LDA
- NIF: 5410002342
- Fatura: 1971
- Data: 23/09/2025
- Vencimento: 23/09/2025
- Subtotal / Total Ilíquido / Montante Tributável: Kz 20.614.000,05
- IVA: Kz 2.885.960,01
- Total a pagar: Kz 23.499.960,06
- Moeda: AOA/KZ

### Correções técnicas
1. O fornecedor passa a ser procurado primeiro no cabeçalho legal, evitando capturar “Vendedor: Bernardo Xavier”.
2. “N.º Contribuinte” passa a ser reconhecido como NIF.
3. “Fatura Nº FT FC2025A/1 971 MINSAUDE” passa a ser normalizado para o número de negócio 1971.
4. O total passa a privilegiar “Total a pagar”, evitando confundir a linha “TOTAL 137 ...” da tabela de itens.
5. Subtotal/IVA são obtidos preferencialmente do resumo fiscal.
6. “O.S.” só é aceite quando seguido de número; palavras OCR como “tal” não são tratadas como Ordem de Saque.
7. Se uma fatura existente for identificada de forma inequívoca, o sistema pode herdar o Acordo-Quadro e o contrato dessa fatura para a reconciliação.
8. A reconciliação de Ordem de Saque consulta também pagamentos antigos cujo meio é “Ordem de Saque” e cujo número está no campo de recibo/referência.
9. O tipo de contratação do fornecedor é pré-preenchido quando já existe no cadastro.
10. Mantém-se o OCR de baixo consumo: uma passagem por página, limite de dimensão, limite de páginas, timeout e libertação de memória.
