# ChivuGest — Melhoria do cruzamento de Documentos Fonte (v13)

## Alterações
- O cruzamento deixa de depender exclusivamente do número da factura.
- Quando a factura não vem identificada no DocFonte, o sistema procura por:
  - fornecedor + valor;
  - fornecedor + valor + data, quando existirem várias candidatas.
- Tolerância de valor de 1% para correspondência automática.
- Associação automática somente quando a correspondência é inequívoca.
- Quando existem várias candidatas sem critério inequívoco, o documento permanece `Por conferir`, evitando associação indevida.
- O botão `Cruzar` volta a executar esta lógica completa sobre cada Documento Fonte.
- A factura encontrada passa a preencher a relação do Documento Fonte com fornecedor/contrato/Acordo-Quadro quando aplicável.

## Regra de segurança
O DocFonte continua a ser apenas documento-fonte para rastreabilidade. Nenhuma importação de DocFonte cria automaticamente Ordem de Saque ou pagamento.
