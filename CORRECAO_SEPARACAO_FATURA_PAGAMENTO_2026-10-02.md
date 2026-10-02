# Correção — Separação entre Importação de Fatura e Pagamento

## Regra funcional
A importação inteligente regista e reconhece apenas os dados documentais da fatura.
Pagamento, método de pagamento, referência de pagamento e Ordem de Saque pertencem aos módulos de Pagamentos/Ordens de Saque.

## Alterações
- Removidos da área **Dados da fatura reconhecidos** os campos Pago, Método de pagamento, Referência de pagamento e Ordem de Saque.
- A reconciliação continua a consultar pagamentos e OS existentes, mas apenas para informação de conferência.
- A confirmação da importação não cria `SupplierPayment` nem `PaymentOrder`.
- Nova fatura importada inicia com `paid=0` e estado `Pendente`.
- Pagamento existente é apresentado separadamente e somente se houver correspondência.
- Ordem de Saque encontrada é apresentada como resultado da reconciliação, sem ser inventada pelo OCR.
- A validação matemática continua a comparar Subtotal + IVA = Total.
