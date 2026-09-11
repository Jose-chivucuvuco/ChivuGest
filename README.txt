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
