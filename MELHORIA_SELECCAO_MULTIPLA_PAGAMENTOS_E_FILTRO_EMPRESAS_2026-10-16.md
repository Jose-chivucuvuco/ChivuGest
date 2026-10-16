# Melhoria — selecção múltipla de pagamentos e filtro de empresas (2026-10-16)

## Pagamentos registados
- Adicionada caixa de selecção por pagamento e opção «Seleccionar todos».
- Adicionado contador dos pagamentos seleccionados e acção «Eliminar seleccionados».
- Eliminação em lote disponível apenas para administradores, com confirmação e registo de auditoria.
- Pagamentos com dependências que impeçam a eliminação são preservados e reportados; os restantes podem ser eliminados.

## Importação DocFonte
- Mantida a parametrização `_is_company_docfonte_row`: exclui contribuintes singulares, categoria Pessoal, salários/vencimentos/remunerações, IRT, segurança social, subsídios do pessoal e ajudas de custo/deslocações/diárias.
- Mantém registos empresariais/institucionais (incluindo colectivos e estrangeiros) que não estejam classificados como pessoal ou subsídios.
- O filtro é aplicado linha a linha durante a importação; os registos excluídos não são importados para o fluxo de empresas/pagamentos.
