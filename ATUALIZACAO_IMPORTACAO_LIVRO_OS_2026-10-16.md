# Actualização — Importação do Livro de Ordem de Saque (16/10/2026)

## Alterações
- Detecta automaticamente PDFs cujo conteúdo identifica o documento como “Livro de Ordem de Saque”, mesmo que o selector esteja em DocFonte.
- Processa as linhas do Livro de OS pelo leitor específico do SIGFE, em vez de criar um único documento genérico.
- Mapeia Nº Doc para Nº OS, Situação, Data, Beneficiário, Valor e Finalidade.
- A Finalidade é guardada como campo auxiliar de reconciliação; só tenta extrair número de factura quando a descrição contém indicação explícita de Fatura/Factura/FT/FA. Referências DLI não são tratadas como números de factura.
- O filtro de categorias de pessoal/salários do DocFonte não é aplicado ao Livro de OS, que não tem esses campos de classificação.
- A importação DocFonte deixa de apagar automaticamente OS legadas; essa limpeza permanece uma acção administrativa explícita.
- Uma importação anterior genérica não deve impedir a criação das OS operacionais quando o PDF for reprocessado no tipo correcto; OS já existentes para o mesmo fornecedor continuam protegidas contra duplicação.

## Limitação de validação
Foi validada a compilação sintáctica. O teste integral com a base de dados real deve ser realizado em ambiente de testes antes de produção.
