# Melhoria — Documentos Fonte e reconciliação

## Objectivo
Transformar "Documentos Fonte Importados" numa área de rastreabilidade e reconciliação, sem confundir dados de origem com Ordens de Saque ou pagamentos operacionais.

## Alterações
- Documento Fonte passa a guardar `reconciliation_status` e `reconciliation_notes`.
- Importação DocFonte continua sem criar OS/pagamentos.
- Tabela passa a mostrar: Documento, Tipo, Fornecedor, Factura, Data, Valor, Confiança, Situação e Acções.
- Acções disponíveis: Ver, Cruzar, Associar factura e Confirmar.
- "Cruzar" executa novamente o motor de correspondência.
- "Associar" permite seleccionar manualmente uma factura do mesmo fornecedor.
- Divergência de valor é registada como "Divergência de valor".
- "Confirmar" marca a revisão manual como "Conferido" sem criar pagamento/OS.
- Documentos Fonte permanecem preservados após o cruzamento para auditoria e rastreabilidade.
- Foram adicionadas migrações aditivas para instalações existentes.
