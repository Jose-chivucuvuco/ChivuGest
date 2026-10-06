# Correção DocFonte — supplier_id NULL (2026-10-06)

## Erro
`psycopg2.errors.NotNullViolation: null value in column "supplier_id" of relation "payment_order" violates not-null constraint`

## Causa
Durante a importação em lote, quando um fornecedor não era encontrado, o código criava um objeto `Supplier` novo com `db.session.add()`, mas tentava ler `supplier.id` antes de executar `flush()`. Assim, `supplier.id` permanecia `None` e o `bulk_insert_mappings(PaymentOrder, ...)` tentava gravar `supplier_id = NULL`.

## Correção
Depois de criar/enfileirar um fornecedor novo, o importador executa `db.session.flush()` antes de construir os mappings de `SourceDocument` e `PaymentOrder`, garantindo que todos os fornecedores pendentes tenham IDs.

Também foi adicionada uma validação explícita para impedir que uma OS seja inserida com `supplier_id` nulo.

## Resultado esperado
O DocFonte pode continuar a ser importado numa única operação, com fornecedores existentes ou novos, sem `NotNullViolation` na coluna `payment_order.supplier_id`.
