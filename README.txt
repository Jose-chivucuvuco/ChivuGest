CHIVUGEST — VERSÃO PROFISSIONAL / CONTRATAÇÃO PÚBLICA

Esta versão amplia o ChivuGest para:
- Dashboard executivo;
- Fornecedores com tipo de contratação obrigatório;
- Faturas e pagamentos de fornecedores;
- Conta corrente por fornecedor;
- Gestão de contratos em vigor e por regularizar;
- Gestão de procedimentos de contratação pública;
- Motor de alertas de conformidade;
- Relatórios;
- Utilizadores e configurações;
- Base legal versionada;
- Importação CSV/XLSX;
- Importação PDF digital, PDF escaneado e imagens com OCR;
- Detecção de documentos duplicados por hash;
- Revisão humana antes de lançar uma fatura importada.

BASE LEGAL DE REFERÊNCIA

A lógica inicial considera a Lei n.º 41/20, de 23 de Dezembro — Lei dos Contratos Públicos, e as Regras de Execução do OGE 2026 aprovadas pelo Decreto Presidencial n.º 74/26, de 23 de Abril. Também são referenciados o Decreto Presidencial n.º 77/23 e o Plano Estratégico da Contratação Pública Angolana 2024–2028.

IMPORTANTE: os limites e regras legais podem ser alterados por OGE, regulamento ou diploma posterior. Por isso, os parâmetros críticos ficam gravados em LegalRule e podem ser atualizados no menu Configurações pelo administrador. O sistema é um mecanismo de apoio à conformidade e não substitui parecer jurídico, despacho do órgão competente, fiscalização do SNCP ou do Tribunal de Contas.

PRIMEIRO ACESSO
Utilizador: admin
Senha: admin123

ALTERAR A SENHA
Antes de uso real, altere a senha inicial. Recomenda-se também implementar MFA, recuperação de senha e política de expiração de senha antes de produção crítica.

DADOS / POSTGRESQL
A versão usa PostgreSQL quando DATABASE_URL está definida. db.create_all() cria as novas tabelas sem apagar as tabelas existentes; a versão nova é aditiva para preservar os dados anteriores.

OCR NO RENDER
O Dockerfile instala tesseract-ocr, tesseract-ocr-por e tesseract-ocr-eng.


CORREÇÃO OOM/OCR: processamento OCR limitado a imagens de 2600 px, PDF até 20 páginas, 1.5 DPI, escala de cinza e recolha de memória; upload máximo 20 MB.


ACTUALIZAÇÃO CONSOLIDADA — 29/09/2026

Esta versão inclui:
- Faturas simplificadas: Nº, fornecedor, contrato opcional, emissão e valor.
- Subtotal, IVA e vencimento retirados do formulário manual de registo; os campos antigos permanecem na base de dados para compatibilidade com importações/histórico.
- Pagamentos continuam a actualizar automaticamente o valor pago e o estado da fatura.
- Gestão de Contratos reorganizada e com preenchimento automático a partir do procedimento associado.
- Gestão de Contratos calcula Faturado, Pago, Saldo e % de execução com base nas faturas/pagamentos ligados ao contrato.
- Contratação Pública organizada em Identificação, Execução e Conformidade.
- Base legal com versões, exercício, entrada em vigor, histórico de verificações e detecção de alterações nas fontes.
- A verificação de fontes legais não interpreta automaticamente uma alteração como nova regra. Alterações detectadas ficam sujeitas a validação humana antes da alteração dos parâmetros.
- Verificação automática opcional: AUTO_LEGAL_CHECK=true; LEGAL_CHECK_INTERVAL_HOURS=6.


ACTUALIZAÇÃO — GESTÃO ACRUADA DE ACORDOS-QUADRO / CONTRATOS — 01/10/2026

- Acordo-Quadro permanece como entidade autónoma e pode existir sem contratos associados.
- Um Acordo-Quadro é registado uma única vez e pode ter vários fornecedores participantes.
- O cadastro de Contratos continua separado do cadastro de Acordos-Quadro.
- Um contrato pode ser independente ou decorrer de um Acordo-Quadro.
- Quando um contrato é associado a um Acordo-Quadro, o ChivuGest limita o fornecedor aos participantes desse acordo.
- O instrumento do contrato é identificado automaticamente como "Contrato ao abrigo de Acordo-Quadro".
- O sistema impede que um contrato seja associado a um Acordo-Quadro no qual o fornecedor não participa.
- O sistema impede que seja usado o instrumento "Contrato ao abrigo de Acordo-Quadro" sem seleccionar o Acordo-Quadro.
- A listagem de Acordos-Quadro mostra quantos contratos estão associados, inclusive zero.
