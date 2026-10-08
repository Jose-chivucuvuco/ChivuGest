# Correção — DocFonte não cria Ordens de Saque

## Problema
Após a importação do DocFonte, as linhas do relatório eram gravadas simultaneamente como `SourceDocument` e `PaymentOrder`. Isso fazia com que as OS do documento-fonte aparecessem no módulo de Pagamentos em “Ordens de saque importadas e cruzadas”.

## Correção
- DocFonte passa a ser tratado como documento-fonte de análise/rastreabilidade.
- A importação de DocFonte não cria `PaymentOrder` e não cria pagamentos.
- As OS legadas anteriormente criadas pelo DocFonte podem ser removidas através da ação administrativa **“Limpar OS legadas do DocFonte”**.
- Os `SourceDocument` são preservados para rastreabilidade.
- A área de Pagamentos passa a ocultar qualquer `PaymentOrder` com `source_type=DocFonte`.
- Livros/ficheiros explicitamente importados como **Livro de Ordens de Saque** ou **Ordem de Saque** mantêm o comportamento de OS operacional.
- Registos de salários, pessoal e subsídios de deslocação continuam excluídos do DocFonte empresarial.

## Validação
O smoke test do ficheiro SIGFE usado anteriormente identificou 3.173 linhas, sendo 2.918 com número de OS. A alteração não muda a leitura dos campos; muda apenas o destino dos dados: DocFonte -> `SourceDocument`, sem `PaymentOrder`.
