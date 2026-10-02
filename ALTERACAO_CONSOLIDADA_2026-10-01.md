# ChivuGest — atualização consolidada de inconsistências

## Principais correções

1. O motor de conformidade é executado **antes** da contagem dos alertas no Dashboard. Isso corrige o caso em que um Acordo-Quadro já está acima de 100% e o Dashboard continuava a mostrar 0 alertas críticos.
2. Acordos-Quadro com faturação/executado >= 100% geram alerta `CRITICO`.
3. Acordos-Quadro entre 90% e 99,99% geram alerta preventivo `ALERTA`.
4. Contratos com faturação >= 100% do valor actual geram alerta `CRITICO`.
5. Contratos entre 90% e 99,99% geram alerta preventivo `ALERTA`.
6. O cálculo mantém percentagens superiores a 100% visíveis; não há truncamento para 100%.
7. `Por executar` não esconde mais o excesso: quando a execução ultrapassa o limite, o Dashboard mostra `Por executar = Kz 0,00` e uma coluna `Excesso` com o valor ultrapassado.
8. A análise por empresa deixou de apresentar `0%` quando não existe contrato/limite individual. Nesses casos mostra `N/D`.
9. Foi criado suporte para **limite atribuído por fornecedor dentro de cada Acordo-Quadro**, permitindo calcular execução individual quando esse limite for informado.
10. Foi acrescentado alerta quando a soma dos limites atribuídos aos fornecedores ultrapassa o limite global do Acordo-Quadro.
11. Pagamentos superiores ao total da fatura são rejeitados no registo e também são identificados pelo motor de conformidade para dados históricos.
12. Faturas duplicadas por fornecedor/número passam a ser rejeitadas no registo e identificadas como alerta quando existirem em dados históricos.
13. O gráfico de pagamentos mensais passa a mostrar o valor do mês além da barra.
14. O painel de alertas identifica o âmbito do alerta: Acordo-Quadro, contrato, procedimento ou fornecedor.
15. A análise de Acordo-Quadro por empresa distingue `limite atribuído` de `limite global`, evitando repetir o limite global do AQ como se fosse limite de cada fornecedor.

## Regras de execução

- `< 90%`: sem alerta de limite.
- `>= 90% e < 100%`: alerta preventivo.
- `>= 100%`: alerta crítico.

## Exemplo dos dados do AQ 126

- Limite: Kz 181.000.000,00
- Faturado/executado: Kz 191.499.960,00
- Excesso: Kz 10.499.960,00
- Execução: 105,80%
- Resultado esperado: 1 alerta crítico de limite ultrapassado.

## Nota de validação

Foi feita validação de sintaxe Python (`py_compile`) do `app.py`. Não foi possível executar o servidor neste ambiente porque as dependências Flask/SQLAlchemy do projeto não estão instaladas localmente e o ambiente não possui acesso à Internet para as instalar. O ZIP entregue contém o código e os templates atualizados.
