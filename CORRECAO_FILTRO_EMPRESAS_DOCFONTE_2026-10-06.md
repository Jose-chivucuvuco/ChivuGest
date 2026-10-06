# Correção — DocFonte: apenas dados de empresas

O importador do ChivuGest passa a excluir automaticamente registos de pessoal/folha salarial e subsídios de deslocação.

Critérios SIGFE utilizados:
- `Tipo do Contribuinte = Singular` → excluído;
- `Categoria = Pessoal` → excluído;
- `Tipo OS` contendo salários/vencimentos/remunerações/subsídios do pessoal/IRT/segurança social/abono de família → excluído;
- `Tipo OS` contendo subsídios de deslocação/ajuda de custo/diárias → excluído;
- `Natureza` com os mesmos termos → excluído.

São mantidos os registos organizacionais, incluindo contribuintes Colectiva, Instituição e Estrangeiro, desde que não sejam classificados como pessoal/folha salarial/deslocação.

Teste com o DocFonte fornecido:
- 3.173 linhas de dados;
- 1.051 linhas mantidas como dados empresariais/organizacionais;
- 2.122 linhas excluídas;
- 863 OS empresariais/organizacionais reconhecidas entre as linhas mantidas.

A importação continua a ser feita num único ficheiro e todos os fornecedores empresariais são processados automaticamente.
