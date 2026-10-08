# Correção v15 — erro Decimal/float na confirmação do Documento Fonte

Corrigido o erro ocorrido ao confirmar um Documento Fonte:
`unsupported operand type(s) for +: 'float' and 'decimal.Decimal'`.

A rotina de confirmação convertia valores financeiros através de `money()` (float) e depois tentava somá-los/subtraí-los com `Decimal` usado pelos campos `Numeric` do SQLAlchemy.

A correção é localizada na confirmação do Documento Fonte: `amount`, `total`, `current_paid` e `remaining` passam a ser normalizados como `Decimal` antes das operações financeiras.

Mantém-se:
- não criar pagamentos na importação do DocFonte;
- criar pagamento apenas na confirmação explícita;
- impedir duplicação pelo recibo/documento fonte;
- actualizar `invoice.paid` e o estado da factura.
