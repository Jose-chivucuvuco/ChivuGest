# Correção do importador DocFonte SIGFE — 2026-10-06

## Problema reproduzido

O DocFonte SIGFE analisado possui 79 colunas. O importador anterior limitava a leitura a 40 colunas (`CHIVUGEST_IMPORT_MAX_COLUMNS=40`).

No ficheiro real:

- `Beneficiário`: coluna 14
- `Data Emissão OS`: coluna 29
- `Nº OS`: coluna 44
- `Situação OS`: coluna 46
- `Valor da OS MN`: coluna 53
- `Valor Total MN`: coluna 55
- `Data da Confirmação de Pagamento`: coluna 72
- `Finalidade da OS`: coluna 73
- `Nº Contrato`: coluna 79

Assim, o importador não chegava a ler `Nº OS`, `Situação OS`, valores e finalidade, provocando a mensagem de que não existiam linhas reconhecíveis.

## Correções aplicadas

1. Aumentado o limite mínimo de leitura de colunas para 100.
2. Adicionado suporte ao cabeçalho `Beneficiário`.
3. Adicionado reconhecimento de `Nº OS` / `Nº OS` normalizado como `n_os`.
4. `Beneficiário` é separado em NIF + nome quando estiver no formato `NIF - Nome`.
5. `Valor Total MN` passou a ser a primeira fonte de valor; `Valor da OS MN` é fallback.
6. `Data Emissão OS` é usada como data principal; `Data da Confirmação de Pagamento` é fallback quando a primeira não existe.
7. `Situação OS` é preservada.
8. `Finalidade da OS` é lida e usada para tentar extrair o número da factura.
9. Foram adicionadas variantes de factura como `Fatura n.º ...` e `Ft. N.º ...`.
10. `Nº Bancário` e `Nº Contrato` foram mapeados.
11. Datas do SIGFE com hora (`dd/mm/yyyy hh:mm:ss`) passaram a ser aceites.
12. Linhas sem Nº OS continuam a ser ignoradas individualmente; não fazem a importação inteira falhar.

## Teste contra o DocFonte fornecido

O ficheiro de teste possui 3.173 linhas de dados, das quais:

- 2.918 têm Nº OS;
- 255 não têm Nº OS;
- 2.918 têm Beneficiário reconhecido;
- 2.918 têm Situação OS reconhecida;
- 2.918 têm Finalidade da OS reconhecida.

O teste confirmou que a coluna `Nº OS` passa a ser alcançável pelo importador.

## Comportamento esperado

Um único DocFonte pode conter vários fornecedores. O ChivuGest importa o ficheiro de uma só vez e percorre as linhas individualmente, associando cada OS ao fornecedor identificado. Não é necessário gerar um ficheiro por fornecedor.

## Limitação de validação neste ambiente

Foi validada a leitura e normalização do XLSX e a compilação (`py_compile`) do `app.py`. Não foi possível executar a aplicação Flask completa neste ambiente porque as dependências Flask/SQLAlchemy não estão instaladas e não há acesso à Internet para instalá-las.
