# Correção — erro `excluded_non_company` (16/10/2026)

## Sintoma
A importação podia terminar com `cannot access local variable 'excluded_non_company' where it is not associated with a value` quando o ficheiro seguia o ramo de extração genérica, fora do processamento CSV/XLSX/Livro de OS estruturado.

## Correção
Inicializar `excluded_non_company = 0` no início do processamento da importação, antes da seleção dos ramos. O contador continua a ser incrementado quando linhas de pessoal/salários/subsídios são filtradas no fluxo estruturado; nos outros fluxos permanece zero.

## Validação
`python -m py_compile app.py` concluído sem erros. Requer teste funcional no ambiente da aplicação com os formatos utilizados pelo utilizador.
