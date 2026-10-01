# ChivuGest — Análise por Empresas — 2026-10-01

## Implementado
- Nova área **Análise por Empresas** (`/supplier-analysis`).
- Filtro por empresa fornecedora.
- Comparação por empresa de Acordos-Quadro, contratos, valor contratual, faturação, pagamentos, saldo por pagar e grau de execução.
- Dashboard passou a apresentar um quadro resumido de análise por empresas.
- Acordos-Quadro são contados como relações da empresa, sem somar repetidamente o valor limite do acordo entre os participantes.
- Grau de execução por empresa = faturado / valor actual dos contratos, limitado a 100% para a barra visual.
- Menu lateral ganhou acesso directo a **Análise por Empresas**.

## Interpretação
- **Valor contratual:** soma do valor actual dos contratos da empresa.
- **Faturado:** soma das faturas da empresa.
- **Pago:** soma dos pagamentos registados para a empresa.
- **Por pagar:** faturado menos pago.
- **Execução:** faturado em relação ao valor contratual.
- Empresas com faturação directa ao Acordo-Quadro mas sem contrato apresentam execução financeira na análise, mas sem base contratual para calcular um percentual de execução contratual.
