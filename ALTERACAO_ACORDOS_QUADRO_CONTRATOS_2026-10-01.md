# Alteração — Acordos-Quadro e Contratos

## Regra implementada

O Acordo-Quadro é uma entidade autónoma. O seu cadastro não cria nem exige um contrato.

Um contrato pode:
1. ser independente; ou
2. ser registado como contrato ao abrigo de um Acordo-Quadro.

## Relação

`Acordo-Quadro → Fornecedores participantes → Contratos associados → Faturas → Pagamentos`

## Validações

- O Acordo-Quadro é cadastrado uma única vez.
- Vários fornecedores podem participar no mesmo Acordo-Quadro.
- Um Acordo-Quadro pode ter zero, um ou vários contratos associados.
- Ao seleccionar um Acordo-Quadro no contrato, apenas os seus fornecedores participantes podem ser escolhidos.
- A aplicação identifica o instrumento como `Contrato ao abrigo de Acordo-Quadro`.
- Não é permitido usar `Contrato ao abrigo de Acordo-Quadro` sem seleccionar o respectivo Acordo-Quadro.
- Não é permitido associar um fornecedor que não participe no Acordo-Quadro.

## Compatibilidade

A alteração utiliza os campos e tabelas de Acordo-Quadro já existentes nesta versão e não elimina os dados anteriores.
