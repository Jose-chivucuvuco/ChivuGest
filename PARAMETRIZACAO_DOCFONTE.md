# Parametrização consolidada do DocFonte

Colunas de origem utilizadas:
1. **Beneficiário**: identifica o fornecedor; quando vem no formato `NIF - Nome`, o sistema tenta separar os campos.
2. **Nº OS**: identificador da Ordem de Saque e chave de deduplicação do pagamento por fornecedor.
3. **Situação OS**: só a situação normalizada como `Paga` pode gerar pagamento.
4. **Valor Total MN**: valor do pagamento confirmado.
5. **Data da Confirmação de Pagamento**: data efectiva do pagamento. Para DocFonte, a data de emissão da OS nunca é substituta.
6. **Finalidade da OS**: campo técnico auxiliar para localizar referência(s) de factura e cruzar OS, fornecedor e factura; não é apresentado como campo separado no pagamento.

Regras:
- Situação diferente de `Paga`: fica como documento de origem e não cria pagamento.
- Situação `Paga` sem data de confirmação: fica para revisão e não cria pagamento.
- Deduplicação: fornecedor + Nº OS.
- Se a finalidade indicar várias facturas, a associação automática deve ser revista para evitar atribuir o total da OS a uma única factura.
- Mantém-se a exclusão já existente de linhas de salários, pessoal e subsídios.
