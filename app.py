import os, csv, io, re, json, hashlib, secrets, unicodedata, urllib.request, urllib.error, xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from functools import wraps
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.datastructures import FileStorage
from sqlalchemy import func, inspect, text, or_, and_
from sqlalchemy.exc import IntegrityError

try:
    import fitz
except ImportError:
    fitz = None
try:
    import pytesseract
except ImportError:
    pytesseract = None
try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None
from PIL import Image
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

database_url = os.environ.get("DATABASE_URL", "sqlite:///chivugest.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# -----------------------------------------------------------------------------
# Existing entities kept for backwards compatibility with the first ChivuGest
# release. The new procurement/supplier layer is additive and does not delete
# existing data.
# -----------------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="user")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    nif = db.Column(db.String(30))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(80), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    paid = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="Pendente")
    client = db.relationship("Client", backref="invoices")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt = db.Column(db.String(80), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"))
    date = db.Column(db.Date, nullable=False)
    method = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    client = db.relationship("Client", backref="payments")
    invoice = db.relationship("Invoice", backref="payments")

# -----------------------------------------------------------------------------
# Supplier / procurement / contract management
# -----------------------------------------------------------------------------
class FrameworkAgreement(db.Model):
    __tablename__ = "framework_agreement"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False, unique=True, index=True)
    object = db.Column(db.Text, nullable=False)
    procedure_type = db.Column(db.String(80), nullable=False, default="Concurso Limitado por Convite")
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    estimated_value = db.Column(db.Numeric(18,2), default=0)
    status = db.Column(db.String(40), default="Em vigor")
    legal_basis = db.Column(db.String(250))
    document_ref = db.Column(db.String(300))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

framework_supplier = db.Table(
    "framework_supplier",
    db.Column("framework_id", db.Integer, db.ForeignKey("framework_agreement.id", ondelete="CASCADE"), primary_key=True),
    db.Column("supplier_id", db.Integer, db.ForeignKey("supplier.id", ondelete="CASCADE"), primary_key=True),
    db.Column("allocated_value", db.Numeric(18,2), nullable=False, default=0),
)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(220), nullable=False, index=True)
    nif = db.Column(db.String(40), index=True)
    phone = db.Column(db.String(60))
    email = db.Column(db.String(180))
    address = db.Column(db.String(300))
    category = db.Column(db.String(120))
    contracting_type = db.Column(db.String(80), nullable=False)
    portal_status = db.Column(db.String(80), default="Não verificado")
    certification_status = db.Column(db.String(80), default="Não informado")
    tax_clearance_expiry = db.Column(db.Date)
    social_security_expiry = db.Column(db.Date)
    professional_license_expiry = db.Column(db.Date)
    blocked = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    framework_agreements = db.relationship("FrameworkAgreement", secondary=framework_supplier, backref=db.backref("suppliers", lazy="dynamic"))

class ProcurementProcedure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False, unique=True)
    object = db.Column(db.Text, nullable=False)
    contract_category = db.Column(db.String(60), nullable=False, default="Bens")
    procedure_type = db.Column(db.String(80), nullable=False)
    estimated_value = db.Column(db.Numeric(18,2), nullable=False, default=0)
    budget_year = db.Column(db.Integer, default=lambda: date.today().year)
    budgeted = db.Column(db.Boolean, default=False)
    cabimentado = db.Column(db.Boolean, default=False)
    cabimentacao_ref = db.Column(db.String(120))
    decision_date = db.Column(db.Date)
    invitation_date = db.Column(db.Date)
    proposal_deadline = db.Column(db.Date)
    adjudication_date = db.Column(db.Date)
    portal_registered = db.Column(db.Boolean, default=False)
    legal_basis = db.Column(db.String(250))
    justification = db.Column(db.Text)
    status = db.Column(db.String(50), default="Em preparação")
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))
    instrument_type = db.Column(db.String(100), default="Contrato público")
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    framework_agreement = db.relationship("FrameworkAgreement", backref="procedures")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier")
    creator = db.relationship("User")

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(100), nullable=False, unique=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    procedure_id = db.Column(db.Integer, db.ForeignKey("procurement_procedure.id"))
    object = db.Column(db.Text, nullable=False)
    contract_type = db.Column(db.String(80), nullable=False)
    procedure_type = db.Column(db.String(80), nullable=False)
    instrument_type = db.Column(db.String(100), default="Contrato público")
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    framework_agreement = db.relationship("FrameworkAgreement", backref="contracts")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    original_value = db.Column(db.Numeric(18,2), nullable=False, default=0)
    current_value = db.Column(db.Numeric(18,2), nullable=False, default=0)
    renewal_allowed = db.Column(db.Boolean, default=False)
    renewal_count = db.Column(db.Integer, default=0)
    cabimentado = db.Column(db.Boolean, default=False)
    cabimentacao_ref = db.Column(db.String(120))
    tribunal_review_required = db.Column(db.Boolean, default=False)
    tribunal_review_status = db.Column(db.String(60), default="Não aplicável")
    guarantee_required = db.Column(db.Boolean, default=False)
    guarantee_value = db.Column(db.Numeric(18,2), default=0)
    advance_percent = db.Column(db.Numeric(7,2), default=0)
    amendments_percent = db.Column(db.Numeric(7,2), default=0)
    status = db.Column(db.String(40), default="Em vigor")
    document_ref = db.Column(db.String(300))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", backref="contracts")
    procedure = db.relationship("ProcurementProcedure", backref="contracts")

class SupplierInvoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(100), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"))
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    subtotal = db.Column(db.Numeric(18,2), default=0)
    vat = db.Column(db.Numeric(18,2), default=0)
    total = db.Column(db.Numeric(18,2), nullable=False, default=0)
    paid = db.Column(db.Numeric(18,2), nullable=False, default=0)
    currency = db.Column(db.String(10), default="AOA")
    status = db.Column(db.String(30), default="Pendente")
    source_filename = db.Column(db.String(255))
    source_hash = db.Column(db.String(64), unique=True)
    raw_text = db.Column(db.Text)
    extracted_data = db.Column(db.Text)
    import_confidence = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", backref="invoices")
    contract = db.relationship("Contract", backref="invoices")
    framework_agreement = db.relationship("FrameworkAgreement", backref="invoices")

class SupplierPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt = db.Column(db.String(100), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("supplier_invoice.id"))
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"))
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    date = db.Column(db.Date, nullable=False)
    method = db.Column(db.String(60), nullable=False)
    amount = db.Column(db.Numeric(18,2), nullable=False)
    reference = db.Column(db.String(150))
    notes = db.Column(db.Text)
    supplier = db.relationship("Supplier", backref="payments")
    invoice = db.relationship("SupplierInvoice", backref="payments")
    contract = db.relationship("Contract", backref="payments")
    framework_agreement = db.relationship("FrameworkAgreement", backref="payments")

class PaymentOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    os_number = db.Column(db.String(120), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("supplier_invoice.id"))
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"))
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    issue_date = db.Column(db.Date)
    amount = db.Column(db.Numeric(18,2), default=0)
    status = db.Column(db.String(50), default="Pendente")
    bank_reference = db.Column(db.String(180))
    source_type = db.Column(db.String(40), default="DocFonte")
    source_filename = db.Column(db.String(255))
    source_hash = db.Column(db.String(64), unique=True)
    extracted_data = db.Column(db.Text)
    reconciliation_status = db.Column(db.String(50), default="Por conferir")
    reconciliation_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", backref="payment_orders")
    invoice = db.relationship("SupplierInvoice", backref="payment_orders")
    contract = db.relationship("Contract", backref="payment_orders")
    framework_agreement = db.relationship("FrameworkAgreement", backref="payment_orders")

class SourceDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_type = db.Column(db.String(50), nullable=False)
    document_number = db.Column(db.String(120), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))
    invoice_id = db.Column(db.Integer, db.ForeignKey("supplier_invoice.id"))
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"))
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    source_filename = db.Column(db.String(255), nullable=False)
    source_hash = db.Column(db.String(64), unique=True, nullable=False)
    issue_date = db.Column(db.Date)
    amount = db.Column(db.Numeric(18,2), default=0)
    extracted_data = db.Column(db.Text)
    import_confidence = db.Column(db.Integer, default=0)
    content = db.Column(db.LargeBinary)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", backref="source_documents")
    invoice = db.relationship("SupplierInvoice", backref="source_documents")
    contract = db.relationship("Contract", backref="source_documents")
    framework_agreement = db.relationship("FrameworkAgreement", backref="source_documents")

class LegalRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(220), nullable=False)
    source = db.Column(db.String(250), nullable=False)
    article = db.Column(db.String(80))
    summary = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default="ALERTA")
    active = db.Column(db.Boolean, default=True)
    parameter = db.Column(db.String(80))
    value = db.Column(db.Numeric(18,2))
    source_url = db.Column(db.String(500))
    version = db.Column(db.String(50), default="2026")

class ComplianceAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(80), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="ALERTA")
    title = db.Column(db.String(250), nullable=False)
    message = db.Column(db.Text, nullable=False)
    legal_basis = db.Column(db.String(250))
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"))
    procedure_id = db.Column(db.Integer, db.ForeignKey("procurement_procedure.id"))
    framework_agreement_id = db.Column(db.Integer, db.ForeignKey("framework_agreement.id"))
    resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier")
    contract = db.relationship("Contract")
    procedure = db.relationship("ProcurementProcedure")
    framework_agreement = db.relationship("FrameworkAgreement")

class LegalDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text)
    source_url = db.Column(db.String(500), nullable=False)
    current_version = db.Column(db.String(60), nullable=False)
    active = db.Column(db.Boolean, default=True)

class LegalVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("legal_document.id"), nullable=False)
    version = db.Column(db.String(80), nullable=False)
    exercise = db.Column(db.Integer)
    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)
    source_hash = db.Column(db.String(64))
    source_url = db.Column(db.String(500))
    status = db.Column(db.String(40), default="Vigente")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    document = db.relationship("LegalDocument", backref="versions")

class LegalUpdateCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("legal_document.id"), nullable=False)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    source_hash = db.Column(db.String(64))
    changed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(40), default="Sem alteração")
    message = db.Column(db.Text)
    document = db.relationship("LegalDocument")
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(80))
    record_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user = db.relationship("User")

class BackupRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    kind = db.Column(db.String(30), default="Completo")
    file_name = db.Column(db.String(255))
    sha256 = db.Column(db.String(64))
    size_bytes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="Concluído")
    user = db.relationship("User")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
PROCEDURES = [
    "Concurso Público", "Concurso Limitado por Prévia Qualificação",
    "Concurso Limitado por Convite", "Contratação Simplificada",
    "Procedimento Dinâmico Electrónico", "Contratação Emergencial"
]
CONTRACT_CATEGORIES = ["Empreitada", "Bens", "Serviços", "Bens e Serviços", "Concessão", "Locação", "Outro / Regime especial"]
CONTRACTING_TYPES = PROCEDURES + ["Outro / Regime especial"]
INSTRUMENT_TYPES = ["Contrato público", "Acordo-Quadro", "Contrato ao abrigo de Acordo-Quadro", "Contrato público de aprovisionamento", "Concessão administrativa", "Concessão de obras públicas", "Concessão de serviços públicos", "Concessão de exploração do domínio público", "Parceria Público-Privada", "Outro / Regime especial"]


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("uid"):
            return redirect(url_for("login"))
        u = db.session.get(User, session["uid"])
        if not u or not u.active:
            session.clear(); return redirect(url_for("login"))
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if session.get("role") != "admin":
            flash("Acesso reservado ao administrador.")
            return redirect(url_for("dashboard"))
        return f(*a, **k)
    return w

@app.context_processor
def globals_processor():
    return {"today": date.today(), "procedures": PROCEDURES, "contract_categories": CONTRACT_CATEGORIES,
            "contracting_types": CONTRACTING_TYPES, "instrument_types": INSTRUMENT_TYPES}


def parse_date(v, default="__TODAY__"):
    if v is None or str(v).strip() == "":
        return date.today() if default == "__TODAY__" else default
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: pass
    return default or date.today()


def money(v):
    try: return float(v or 0)
    except Exception: return 0.0


def num(v):
    if v is None or str(v).strip() == "": return 0.0
    s = str(v).strip().upper().replace("AOA", "").replace("AKZ", "").replace("KZ", "").replace("$", "").replace("€", "")
    s = re.sub(r"[^0-9,.-]", "", s)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."): s = s.replace(".", "").replace(",", ".")
        else: s = s.replace(",", "")
    elif "," in s:
        # 1,234.56 was handled above; here comma is normally decimal in Angola/Portugal.
        s = s.replace(",", ".")
    try: return float(s)
    except (ValueError, TypeError): return 0.0


def normalize_key(k):
    if k is None: return ""
    s = unicodedata.normalize("NFKD", str(k)).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    aliases = {
        "factura":"fatura", "n_fatura":"numero", "numero_fatura":"numero", "n_fatura":"numero",
        "invoice_number":"numero", "invoice_no":"numero", "documento":"numero", "doc":"numero",
        "fornecedor":"fornecedor", "supplier":"fornecedor", "nome_fornecedor":"fornecedor", "emitente":"fornecedor",
        "nuit":"nif", "vat_number":"nif", "tax_id":"nif", "tin":"nif",
        "data_emissao":"data", "issue_date":"data", "invoice_date":"data", "data_fatura":"data",
        "due_date":"vencimento", "data_vencimento":"vencimento", "data_limite":"vencimento",
        "valor_total":"total", "total_fatura":"total", "valor":"total", "amount":"total", "grand_total":"total",
        "subtotal":"subtotal", "base_tributavel":"subtotal", "iva":"iva", "vat":"iva", "imposto":"iva",
        "moeda":"currency", "meio_pagamento":"metodo", "payment_method":"metodo", "metodo_pagamento":"metodo",
        "iban":"iban", "referencia":"referencia", "reference":"referencia", "descricao":"descricao", "description":"descricao"
    }
    return aliases.get(s, s)


def row_value(row, *keys):
    normalized = {normalize_key(k): v for k, v in row.items()}
    for key in keys:
        nk = normalize_key(key)
        if nk in normalized and normalized[nk] not in (None, ""):
            return normalized[nk]
    return ""


def normalize_text(text_value):
    return re.sub(r"[ \t]+", " ", text_value.replace("\xa0", " "))


def regex_first(text_value, patterns):
    for p in patterns:
        m = re.search(p, text_value, re.I | re.M)
        if m:
            return m.group(1).strip(" :#-\t")
    return ""


def parse_invoice_text(text_value):
    text_value = normalize_text(text_value)
    number = regex_first(text_value, [
        r"(?:fatura|factura|invoice|documento)\s*(?:n[ºo°]?|no|numero|número|number)?\s*[:#-]?\s*([A-Z]{0,5}[A-Z0-9./_-]{2,})",
        r"\b((?:FT|FA|FR|FAC|INV)[\s./_-]*[A-Z0-9_-]{2,})\b"
    ])
    nif = regex_first(text_value, [r"(?:NIF|NUIT|N\.I\.F\.)\s*[:#-]?\s*([0-9]{8,15})"])
    supplier = regex_first(text_value, [
        r"(?:fornecedor|supplier|emitente|vendedor)\s*[:#-]\s*([^\n\r]{3,120})",
        r"(?:nome|name)\s*[:#-]\s*([^\n\r]{3,120})"
    ])
    dates = re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b", text_value)
    total = regex_first(text_value, [
        r"(?:total a pagar|total da fatura|total factura|total fatura|grand total|valor total|total)\s*[:=\-]?\s*(?:AOA|KZ|AKZ)?\s*([0-9][0-9 .,'-]{1,})",
        r"(?:valor a pagar|montante)\s*[:=\-]?\s*(?:AOA|KZ|AKZ)?\s*([0-9][0-9 .,'-]{1,})"
    ])
    subtotal = regex_first(text_value, [r"(?:subtotal|total liquido|base tributavel)\s*[:=\-]?\s*(?:AOA|KZ|AKZ)?\s*([0-9][0-9 .,'-]{1,})"])
    vat = regex_first(text_value, [r"(?:IVA|VAT)\s*(?:\([0-9]+(?:[.,][0-9]+)?%\))?\s*[:=\-]?\s*(?:AOA|KZ|AKZ)?\s*([0-9][0-9 .,'-]{1,})"])
    iban = regex_first(text_value, [r"\b(\w{2}\d{2}[A-Z0-9 ]{10,34})\b"])
    currency = "AOA" if re.search(r"\b(?:KZ|AOA|AKZ|KWANZA|KWANZAS)\b", text_value, re.I) else ""
    data = {
        "number": number, "supplier": supplier, "nif": nif,
        "date": dates[0] if dates else "", "due_date": dates[1] if len(dates) > 1 else "",
        "subtotal": num(subtotal), "vat": num(vat), "total": num(total), "currency": currency,
        "iban": iban.replace(" ", ""), "text": text_value
    }
    if not data["total"] and data["subtotal"]:
        data["total"] = data["subtotal"] + data["vat"]
    score = 0
    score += 25 if data["number"] else 0
    score += 20 if data["supplier"] else 0
    score += 15 if data["nif"] else 0
    score += 15 if data["date"] else 0
    score += 25 if data["total"] else 0
    data["confidence"] = score
    return data


def extract_invoice_document(file_storage):
    filename=(file_storage.filename or "").lower()
    if filename.endswith((".xml", ".json")):
        raw=file_storage.read(); digest=hashlib.sha256(raw).hexdigest()
        if filename.endswith(".json"):
            obj=json.loads(raw.decode("utf-8-sig"))
            if isinstance(obj, list): obj=obj[0] if obj else {}
            flat=[]
            def walk(x,prefix=""):
                if isinstance(x,dict):
                    for k,v in x.items(): walk(v, f"{prefix}.{k}" if prefix else str(k))
                elif isinstance(x,list):
                    for i,v in enumerate(x): walk(v, f"{prefix}.{i}")
                else: flat.append((prefix,x))
            walk(obj)
            text_json="\n".join(f"{k}: {v}" for k,v in flat)
        else:
            root=ET.fromstring(raw)
            pairs=[]
            for el in root.iter():
                if el.text and el.text.strip(): pairs.append((el.tag.split('}')[-1], el.text.strip()))
            text_json="\n".join(f"{k}: {v}" for k,v in pairs)
        parsed=parse_invoice_text(text_json); parsed.update({"hash":digest,"filename":file_storage.filename})
        # Structured documents often have clearer field names than OCR.
        try:
            if filename.endswith(".json"):
                obj=json.loads(raw.decode("utf-8-sig")); flat_text=json.dumps(obj,ensure_ascii=False)
            else: flat_text=text_json
            parsed["supplier"] = parsed["supplier"] or regex_first(flat_text,[r"(?:SupplierName|Supplier|Fornecedor|Seller)\s*[:=]\s*[\"']?([^,\n\"']+)"])
            parsed["number"] = parsed["number"] or regex_first(flat_text,[r"(?:InvoiceNumber|InvoiceNo|Numero|Fatura|Factura)\s*[:=]\s*[\"']?([A-Z0-9./_-]+)"])
        except Exception:
            pass
        return parsed
    return extract_pdf_or_image(file_storage)


def extract_pdf_or_image(file_storage):
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    digest = hashlib.sha256(raw).hexdigest()
    texts = []
    if filename.endswith(".pdf"):
        if fitz is None: raise ValueError("PyMuPDF não instalado.")
        doc = fitz.open(stream=raw, filetype="pdf")
        for page in doc:
            txt = page.get_text("text") or ""
            if len(re.sub(r"\s+", "", txt)) < 40:
                if pytesseract is None: raise ValueError("OCR não instalado.")
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                try: txt = pytesseract.image_to_string(img, lang="por+eng", config="--psm 6")
                except Exception: txt = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
                img.close()
                del img, pix
            texts.append(txt)
        doc.close()
    elif filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
        if pytesseract is None: raise ValueError("OCR não instalado.")
        img = Image.open(io.BytesIO(raw)).convert("L")
        img.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        try: texts.append(pytesseract.image_to_string(img, lang="por+eng", config="--psm 6"))
        except Exception: texts.append(pytesseract.image_to_string(img, lang="eng", config="--psm 6"))
        img.close()
    else:
        raise ValueError("Formato não suportado para OCR. Use PDF, PNG, JPG, JPEG, WEBP, TIF ou TIFF.")
    parsed = parse_invoice_text("\n".join(texts))
    parsed["hash"] = digest
    parsed["filename"] = file_storage.filename
    return parsed


def uploaded_rows(f):
    name = (f.filename or "").lower()
    if name.endswith(".xlsx"):
        if not load_workbook: raise ValueError("openpyxl não instalado.")
        wb = load_workbook(f, read_only=True, data_only=True)
        ws = wb.active
        data = list(ws.iter_rows(values_only=True)); wb.close()
        if not data: return []
        headers = [normalize_key(x) for x in data[0]]
        return [dict(zip(headers, r)) for r in data[1:] if any(x is not None for x in r)]
    if name.endswith(".csv"):
        raw = f.read()
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try: s = raw.decode(enc); break
            except UnicodeDecodeError: s = None
        if s is None: raise ValueError("Não foi possível ler o CSV.")
        sample = s[:4096]
        try: dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";" if ";" in sample else ","
        # Parse rows explicitly so malformed legacy exports are recoverable.
        # Standard CSV remains fully supported, including quoted supplier names
        # such as "CASA NOVA - HOME & OFFICE, LDA".
        records=list(csv.reader(io.StringIO(s), dialect=dialect))
        if not records: return []
        headers=[normalize_key(x) for x in records[0]]
        out=[]
        for row in records[1:]:
            if not any(str(x).strip() for x in row): continue
            if len(row)==len(headers):
                out.append(dict(zip(headers,row))); continue
            # Repair the legacy ChivuGest 11-column report where commas inside
            # supplier names and an extra numeric zero shifted the columns.
            expected={"fornecedor","nif","acordo_quadro","contrato","fatura","data","vencimento","total","pago","saldo","estado"}
            if set(headers)==expected and len(row)>len(headers):
                nif_idx=next((idx for idx,v in enumerate(row) if re.fullmatch(r"\d{8,14}",str(v).strip())),None)
                if nif_idx is not None and nif_idx>=1:
                    supplier=", ".join(str(v).strip() for v in row[:nif_idx]).strip()
                    tail=row[nif_idx:]
                    # After NIF, the first seven fields through Total are stable.
                    # Recalculate Saldo from Total-Pago rather than trusting the
                    # shifted legacy columns.
                    if len(tail)>=10:
                        data=dict(zip(headers, [supplier]+tail[:10]))
                        data["fornecedor"]=supplier; data["nif"]=tail[0]
                        try:
                            total_val=num(data.get("total")); paid_val=num(data.get("pago"))
                            data["saldo"]=f"{max(total_val-paid_val,0):.2f}"
                            data["estado"]=str(row[-1]).strip() or ("Paga" if total_val<=paid_val else "Pendente")
                            out.append(data); continue
                        except Exception:
                            pass
            # Conservative fallback: keep the first columns rather than silently
            # assigning a shifted NIF or amount to another business field.
            out.append(dict(zip(headers,row[:len(headers)])))
        return out
    raise ValueError("Para tabelas use CSV/XLSX. Para documentos use PDF/imagem.")

def extract_generic_source_document(file_storage):
    """Extracts common DocFonte/ordem de saque fields from tabular or document files."""
    filename=(file_storage.filename or "").lower()
    raw=file_storage.read()
    digest=hashlib.sha256(raw).hexdigest()
    text_value=""
    if filename.endswith((".csv", ".xlsx")):
        # Reuse the flexible table reader with a fresh in-memory upload.
        class FS:
            def __init__(self, name, data): self.filename=name; self._data=data
            def read(self): return self._data
        rows=uploaded_rows(FS(file_storage.filename, raw))
        text_value="\n".join("; ".join(f"{k}: {v}" for k,v in r.items()) for r in rows[:500])
        first=rows[0] if rows else {}
        data={
            "os_number": str(row_value(first,"ordem_saque","ordem_de_saque","os","numero_os","n_os","ordem","numero_ordem","referencia")).strip(),
            "supplier": str(row_value(first,"fornecedor","supplier","emitente","beneficiario")).strip(),
            "nif": str(row_value(first,"nif","nuit","tax_id")).strip(),
            "invoice_number": str(row_value(first,"fatura","factura","numero_fatura","invoice_number","documento")).strip(),
            "date": row_value(first,"data","data_emissao","issue_date","data_os"),
            "amount": num(row_value(first,"valor","valor_os","montante","amount","total")),
            "status": str(row_value(first,"situacao","situação","status","estado") or "Pendente").strip(),
            "bank_reference": str(row_value(first,"referencia_bancaria","referencia_banco","bank_reference","referencia")).strip(),
        }
    elif filename.endswith((".xml", ".json")):
        raw_text=raw.decode("utf-8-sig", errors="ignore")
        if filename.endswith(".json"):
            obj=json.loads(raw_text); obj=obj[0] if isinstance(obj,list) and obj else obj
            flat=[]
            def walk(x,prefix=""):
                if isinstance(x,dict):
                    for k,v in x.items(): walk(v, f"{prefix}.{k}" if prefix else str(k))
                elif isinstance(x,list):
                    for i,v in enumerate(x): walk(v,f"{prefix}.{i}")
                else: flat.append((prefix,x))
            walk(obj); text_value="\n".join(f"{k}: {v}" for k,v in flat)
        else:
            root=ET.fromstring(raw); pairs=[]
            for el in root.iter():
                if el.text and el.text.strip(): pairs.append((el.tag.split('}')[-1],el.text.strip()))
            text_value="\n".join(f"{k}: {v}" for k,v in pairs)
        data={
            "os_number": regex_first(text_value,[r"(?:ordem(?:\s+de)?\s+s[aá]que|OS|numero_ordem|numero_os)\s*[:=#-]?\s*([A-Z0-9./_-]+)" ]),
            "supplier": regex_first(text_value,[r"(?:fornecedor|supplier|benefici[aá]rio|emitente)\s*[:=#-]?\s*([^\n,;]{3,120})"]),
            "nif": regex_first(text_value,[r"(?:NIF|NUIT|tax_id)\s*[:=#-]?\s*([0-9]{8,15})"]),
            "invoice_number": regex_first(text_value,[r"(?:fatura|factura|invoice)\s*(?:n[ºo°]?|numero|number)?\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
            "date": regex_first(text_value,[r"(?:data|date)\s*[:=#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})"]),
            "amount": num(regex_first(text_value,[r"(?:valor|montante|amount|total)\s*[:=#-]?\s*(?:AOA|KZ|AKZ)?\s*([0-9][0-9 .,'-]{1,})"])),
            "status": regex_first(text_value,[r"(?:situa[cç][aã]o|status|estado)\s*[:=#-]?\s*([^\n,;]{3,50})"]) or "Pendente",
            "bank_reference": regex_first(text_value,[r"(?:refer[eê]ncia banc[aá]ria|bank_reference|referencia)\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
        }
    elif filename.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
        class FS:
            def __init__(self,name,data): self.filename=name; self._data=data
            def read(self): return self._data
        parsed=extract_pdf_or_image(FS(file_storage.filename, raw))
        text_value=parsed.get("text","")
        data={
            "os_number": regex_first(text_value,[r"(?:ordem(?:\s+de)?\s+s[aá]que|OS|n[ºo°]\s*OS)\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
            "supplier": parsed.get("supplier","") or regex_first(text_value,[r"(?:fornecedor|benefici[aá]rio|emitente)\s*[:=#-]\s*([^\n]{3,120})"]),
            "nif": parsed.get("nif","") ,
            "invoice_number": parsed.get("number","") ,
            "date": parsed.get("date","") ,
            "amount": parsed.get("total",0),
            "status": regex_first(text_value,[r"(?:situa[cç][aã]o|status|estado)\s*[:=#-]?\s*([^\n]{3,50})"]) or "Pendente",
            "bank_reference": regex_first(text_value,[r"(?:refer[eê]ncia banc[aá]ria|referencia banc[aá]ria|bank)\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
        }
    elif filename.endswith(".txt"):
        text_value=raw.decode("utf-8-sig",errors="ignore")
        data={
            "os_number": regex_first(text_value,[r"(?:ordem(?:\s+de)?\s+s[aá]que|OS)\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
            "supplier": regex_first(text_value,[r"(?:fornecedor|benefici[aá]rio|emitente)\s*[:=#-]?\s*([^\n]{3,120})"]),
            "nif": regex_first(text_value,[r"(?:NIF|NUIT)\s*[:=#-]?\s*([0-9]{8,15})"]),
            "invoice_number": regex_first(text_value,[r"(?:fatura|factura|invoice)\s*(?:n[ºo°]?|numero)?\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
            "date": regex_first(text_value,[r"(?:data|date)\s*[:=#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"]),
            "amount": num(regex_first(text_value,[r"(?:valor|montante|amount|total)\s*[:=#-]?\s*(?:AOA|KZ|AKZ)?\s*([0-9][0-9 .,'-]{1,})"])),
            "status": regex_first(text_value,[r"(?:situa[cç][aã]o|status|estado)\s*[:=#-]?\s*([^\n]{3,50})"]) or "Pendente",
            "bank_reference": regex_first(text_value,[r"(?:refer[eê]ncia|referencia banc[aá]ria)\s*[:=#-]?\s*([A-Z0-9./_-]+)"]),
        }
    else:
        raise ValueError("Formato não suportado. Use CSV, XLSX, PDF, TXT, XML, JSON, PNG, JPG/JPEG, WEBP ou TIFF.")
    data["date_parsed"]=parse_date(data.get("date"), None)
    data["hash"]=digest; data["filename"]=file_storage.filename; data["text"]=text_value[:120000]
    score=sum(bool(data.get(k)) for k in ("os_number","supplier","invoice_number","date","amount"))*20
    if data.get("nif"): score+=10
    data["confidence"]=min(score,100)
    return data

def normalize_os_status(value):
    s=unicodedata.normalize("NFKD",str(value or "Pendente")).encode("ascii","ignore").decode().lower().strip()
    if "anulad" in s: return "Anulada"
    if "devolvid" in s or "rejeitad" in s: return "Devolvida"
    if "pag" in s or "liquid" in s or "efetivad" in s or "efectivad" in s: return "Paga"
    if "process" in s or "banc" in s: return "Em processamento"
    if "emitid" in s or "aprov" in s: return "Emitida"
    return "Pendente"

def _normalize_match_text(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().upper().strip()
    value = re.sub(r"[^A-Z0-9]+", "", value)
    return value

def _invoice_number_keys(value):
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().upper()
    raw = re.sub(r"(?:FATURA|FACTURA|INVOICE)\s*", "", raw)
    raw = re.sub(r"N[Oº°]?\s*", "", raw)
    compact = re.sub(r"[^A-Z0-9]+", "", raw)
    keys={compact} if compact else set()
    nums=re.findall(r"\d+", raw)
    keys.update(nums)
    return {k for k in keys if k}

def _invoice_number_matches(a, b):
    ka, kb = _invoice_number_keys(a), _invoice_number_keys(b)
    return bool(ka and kb and ka.intersection(kb))

def _supplier_match_for_payment_order(order):
    if order.supplier_id:
        supplier=db.session.get(Supplier, order.supplier_id)
        if supplier:
            return supplier
    try:
        data=json.loads(order.extracted_data or "{}")
    except Exception:
        data={}
    nif=str(data.get("nif") or "").strip()
    if nif:
        supplier=Supplier.query.filter_by(nif=nif).first()
        if supplier: return supplier
    name=_normalize_match_text(data.get("supplier"))
    if name:
        for supplier in Supplier.query.all():
            if _normalize_match_text(supplier.name)==name:
                return supplier
    return None

def _reconcile_payment_orders(existing_only=False):
    """Reconcile imported Ordens de Saque with supplier invoices.

    Existing OS records are linked without requiring a new import. Matching priority:
    1) existing invoice_id; 2) supplier + invoice number; 3) supplier + invoice number/amount;
    4) supplier + amount + nearest issue date, only when the candidate is unique.
    """
    changed=0
    orders=PaymentOrder.query.filter(PaymentOrder.invoice_id.is_(None)).all()
    for order in orders:
        supplier=_supplier_match_for_payment_order(order)
        if not supplier:
            continue
        try:
            data=json.loads(order.extracted_data or "{}")
        except Exception:
            data={}
        inv_number=data.get("invoice_number") or ""
        amount=money(order.amount)
        candidates=SupplierInvoice.query.filter_by(supplier_id=supplier.id).all()
        if not candidates:
            continue

        # Strongest match: normalized invoice number. This handles values such as
        # "Fatura Nº 1972", "Factura 1972" and "1972" as the same document.
        by_number=[i for i in candidates if _invoice_number_matches(inv_number, i.number)] if inv_number else []
        chosen=None
        if len(by_number)==1:
            chosen=by_number[0]
        elif len(by_number)>1:
            amount_matches=[i for i in by_number if abs(money(i.total)-amount) <= max(0.01,money(i.total)*0.01)]
            if len(amount_matches)==1: chosen=amount_matches[0]

        # Fallback: unique amount match, preferably with a close issue date.
        if chosen is None:
            amount_matches=[i for i in candidates if abs(money(i.total)-amount) <= max(0.01,money(i.total)*0.01)]
            if len(amount_matches)==1:
                chosen=amount_matches[0]
            elif len(amount_matches)>1 and order.issue_date:
                dated=sorted(amount_matches, key=lambda i: abs((i.issue_date-order.issue_date).days) if i.issue_date else 10**9)
                if len(dated)==1 or (dated[0].issue_date and dated[1].issue_date and abs((dated[0].issue_date-order.issue_date).days) < abs((dated[1].issue_date-order.issue_date).days)):
                    chosen=dated[0]

        if chosen is None:
            continue

        order.invoice_id=chosen.id
        if not order.contract_id and chosen.contract_id: order.contract_id=chosen.contract_id
        if not order.framework_agreement_id:
            order.framework_agreement_id=chosen.framework_agreement_id or (chosen.contract.framework_agreement_id if chosen.contract else None)
        order.reconciliation_status="Conferido"
        order.reconciliation_notes=(order.reconciliation_notes or "") + ("; " if order.reconciliation_notes else "") + "Fatura reconciliada automaticamente no ChivuGest"
        changed+=1
    if changed:
        db.session.commit()
    return changed

def match_payment_order(data):
    supplier=None
    nif=(data.get("nif") or "").strip()
    if nif: supplier=Supplier.query.filter_by(nif=nif).first()
    if not supplier and data.get("supplier"):
        normalized=_normalize_match_text(data.get("supplier"))
        for s in Supplier.query.all():
            if _normalize_match_text(s.name)==normalized:
                supplier=s; break
    invoice=None
    invoice_number=data.get("invoice_number") or ""
    candidates=SupplierInvoice.query.filter_by(supplier_id=supplier.id).all() if supplier else SupplierInvoice.query.all()
    by_number=[i for i in candidates if _invoice_number_matches(invoice_number, i.number)] if invoice_number else []
    if len(by_number)==1:
        invoice=by_number[0]
    elif len(by_number)>1:
        amount=money(data.get("amount"))
        amount_matches=[i for i in by_number if abs(money(i.total)-amount)<=max(0.01,money(i.total)*0.01)]
        if len(amount_matches)==1: invoice=amount_matches[0]
    if not supplier and invoice: supplier=invoice.supplier
    contract=invoice.contract if invoice else None
    notes=[]
    if supplier: notes.append("Fornecedor identificado")
    else: notes.append("Fornecedor não identificado")
    if invoice: notes.append("Fatura identificada por número normalizado")
    else: notes.append("Fatura não identificada")
    amount=money(data.get("amount"))
    if invoice and abs(money(invoice.total)-amount) <= max(0.01, money(invoice.total)*0.01): notes.append("Valor compatível")
    elif invoice: notes.append("Valor divergente")
    status="Conferido" if supplier and invoice and (not invoice.total or abs(money(invoice.total)-amount)<=max(0.01,money(invoice.total)*0.01)) else "Por conferir"
    return supplier,invoice,contract,status,"; ".join(notes)

# -----------------------------------------------------------------------------
# Legal rules and compliance engine. This is a rules assistant, not a legal
# opinion. Thresholds are stored in the DB so administrators can update them
# when the annual OGE/Annex I changes.
# -----------------------------------------------------------------------------
LEGAL_DOCS = [
    ("Lei n.º 41/20 — Lei dos Contratos Públicos", "Regime jurídico da formação e execução dos contratos públicos.", "https://lex.ao/docs/assembleia-nacional/2020/lei-n-o-41-20-de-23-de-dezembro/", "41/20"),
    ("Decreto Presidencial n.º 74/26 — REOGE 2026", "Regras de execução do OGE 2026, incluindo execução de contratos públicos.", "https://www.angolex.com/paginas/decreto-presidencial/regras-de-execucao-do-orcamento-geral-do-estado-para-2026a-74a-26a.html", "74/26"),
    ("Decreto Presidencial n.º 77/23", "Procedimento de cobrança e destino das coimas da contratação pública.", "https://lex.ao/docs/presidente-da-republica/2023/decreto-presidencial-n-o-77-23-de-20-de-marco/", "77/23"),
    ("Decreto Presidencial n.º 250/24", "Plano Estratégico da Contratação Pública Angolana 2024–2028.", "https://lex.ao/docs/presidente-da-republica/2024/decreto-presidencial-n-o-250-24-de-13-de-novembro/", "250/24"),
]

LEGAL_SEEDS = [
    ("LCP_PROC_VALUE", "Escolha do procedimento por valor", "Lei 41/20", "Art. 22.º–25.º", "Concurso Público ou Concurso Limitado por Prévia Qualificação é a regra; Concurso Limitado por Convite e Contratação Simplificada têm limites de valor.", "CRITICO", None, None),
    ("LCP_LOTS", "Valor agregado dos lotes", "Lei 41/20", "Art. 25.º", "Quando prestações do mesmo tipo são divididas em lotes, o valor considerado para escolha do procedimento é o somatório dos valores estimados dos lotes.", "CRITICO", None, None),
    ("LCP_SIMPLIFIED", "Contratação Simplificada por valor", "Lei 41/20", "Art. 24.º/27.º–30.º", "A contratação simplificada por valor não deve exceder o Nível 1 do Anexo I; critérios materiais têm regime próprio.", "CRITICO", "nivel_1", 18000000),
    ("LCP_INVITATION", "Concurso Limitado por Convite", "Lei 41/20", "Art. 24.º", "O Concurso Limitado por Convite só permite contratos abaixo do Nível 5 do Anexo I.", "CRITICO", "nivel_5", 182000000),
    ("LCP_CONCESSION", "Concessões", "Lei 41/20", "Art. 24.º, n.º 5", "Para concessões deve ser adotado Concurso Público ou Concurso Limitado por Prévia Qualificação, independentemente do valor.", "CRITICO", None, None),
    ("LCP_BUDGET", "Decisão de contratar e verba", "Lei 41/20", "Art. 32.º", "A decisão de contratar pressupõe verba inscrita no orçamento, salvo a condição legalmente prevista.", "CRITICO", None, None),
    ("LCP_WRITTEN", "Contrato escrito", "Lei 41/20", "Art. 106.º–107.º", "Regra geral: contrato reduzido a escrito, com exceções legais por valor/natureza.", "ALERTA", None, None),
    ("LCP_BOND", "Caução", "Lei 41/20", "Art. 99.º", "A caução é obrigatória para adjudicações iguais ou superiores ao Nível 5, sem prejuízo de exigência em valor inferior.", "ALERTA", None, None),
    ("LCP_SANCTIONS", "Impedimentos e sanções", "Lei 41/20", "Art. 56.º–57.º e 429.º–438.º", "O sistema deve verificar impedimentos, empresas incumpridoras e situações sancionatórias registadas.", "CRITICO", None, None),
    ("LCP_PAC", "Plano Anual de Contratação", "Lei 41/20", "Art. 442.º", "A entidade pública deve elaborar e comunicar o Plano Anual de Contratação.", "ALERTA", None, None),
    ("REOGE_CAB", "Cabimentação prévia", "DP 74/26", "Art. 9.º–10.º", "É vedado iniciar despesas, obras, contratos ou requisições sem prévia cabimentação nos limites legais.", "CRITICO", None, None),
    ("REOGE_ADV_WORKS", "Adiantamento de empreitada", "DP 74/26", "Art. 10.º", "Adiantamento inicial de empreitada até 15%; até 30% pode ser autorizado pelo responsável das Finanças nos termos do diploma.", "CRITICO", "adiantamento_empreitada", 15),
    ("REOGE_ADV_GOODS", "Pagamento inicial de bens/serviços", "DP 74/26", "Art. 10.º", "Pagamento inicial para bens e serviços de despesas correntes pode ir até 50%, desde que devidamente fundamentado.", "CRITICO", "adiantamento_bens_servicos", 50),
    ("REOGE_AMEND", "Adendas/trabalhos a mais", "DP 74/26", "Art. 10.º", "É proibida adenda resultante de trabalhos a mais quando o valor total excede 15% do contrato inicial, sem prejuízo do regime de reequilíbrio financeiro.", "CRITICO", "adendas", 15),
    ("REOGE_RENEW", "Contratos contínuos", "DP 74/26", "Art. 10.º", "Contratos contínuos podem ser prorrogados em condições legais até ao prazo máximo de 48 meses; depois exige-se novo procedimento.", "CRITICO", "meses_continuos", 48),
    ("REOGE_HIGH_VALUE", "Diligências de beneficiário efetivo", "DP 74/26", "Art. 10.º", "Acima de Kz 500M em empreitadas e Kz 182M em bens/serviços, devem ser observadas as diligências previstas no diploma quando solicitadas pelos bancos.", "ALERTA", "alto_valor_bens_servicos", 182000000),
]


def seed_legal_data():
    for name, desc, url, version in LEGAL_DOCS:
        if not LegalDocument.query.filter_by(name=name).first():
            db.session.add(LegalDocument(name=name, description=desc, source_url=url, current_version=version))
    for code, title, source, article, summary, severity, parameter, value in LEGAL_SEEDS:
        rule = LegalRule.query.filter_by(code=code).first()
        if not rule:
            db.session.add(LegalRule(code=code, title=title, source=source, article=article,
                                     summary=summary, severity=severity, parameter=parameter, value=value,
                                     source_url=next((u for n,d,u,v in LEGAL_DOCS if n.startswith(source)), None)))
    db.session.commit()


def _fetch_legal_source(url, timeout=6):
    """Fetch an authoritative/legal source for change detection only.
    The content is never interpreted automatically as a new legal rule.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "ChivuGest-Legal-Checker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(2_000_000)
        return hashlib.sha256(data).hexdigest(), resp.geturl()

def seed_legal_versions():
    for doc in LegalDocument.query.all():
        if not LegalVersion.query.filter_by(document_id=doc.id).first():
            version = doc.current_version
            year_match = re.search(r"(20\d{2})", version or "")
            short_year = re.search(r"/(\d{2})$", version or "")
            exercise = int(year_match.group(1)) if year_match else (2000 + int(short_year.group(1)) if short_year else date.today().year)
            db.session.add(LegalVersion(
                document_id=doc.id, version=version, exercise=exercise,
                effective_from=date(exercise, 1, 1) if exercise else None,
                source_url=doc.source_url, status="Vigente",
                notes="Versão inicial registada pelo ChivuGest."
            ))
    db.session.commit()

def check_legal_updates():
    """Check configured legal sources and register changes for validation.
    A changed source becomes 'Pendente de validação'; no legal parameter is
    changed automatically from unverified web content.
    """
    results = []
    for doc in LegalDocument.query.filter_by(active=True).all():
        try:
            digest, final_url = _fetch_legal_source(doc.source_url)
            previous = LegalUpdateCheck.query.filter_by(document_id=doc.id).order_by(LegalUpdateCheck.checked_at.desc()).first()
            changed = bool(previous and previous.source_hash and previous.source_hash != digest)
            status = "Alteração detectada — validação necessária" if changed else "Sem alteração"
            message = ("A fonte apresentou conteúdo diferente da última verificação. "
                       "É necessária validação humana antes de alterar regras/limites.")
            if not previous:
                message = "Primeira verificação registada."
            db.session.add(LegalUpdateCheck(document_id=doc.id, source_hash=digest, changed=changed,
                                            status=status, message=message))
            results.append((doc.name, status))
        except Exception as exc:
            db.session.add(LegalUpdateCheck(document_id=doc.id, source_hash=None, changed=False,
                                            status="Erro na verificação", message=str(exc)))
            results.append((doc.name, "Erro na verificação"))
    db.session.commit()
    return results

def maybe_auto_check_legal_updates():
    """Optional automatic source check.
    Enable with AUTO_LEGAL_CHECK=true. The check runs at most once per
    LEGAL_CHECK_INTERVAL_HOURS and never applies unverified rules automatically.
    """
    if os.environ.get("AUTO_LEGAL_CHECK", "false").lower() not in ("1", "true", "yes"):
        return
    try:
        interval = float(os.environ.get("LEGAL_CHECK_INTERVAL_HOURS", "6"))
        latest = LegalUpdateCheck.query.order_by(LegalUpdateCheck.checked_at.desc()).first()
        if latest and (datetime.utcnow() - latest.checked_at).total_seconds() < interval * 3600:
            return
        check_legal_updates()
    except Exception:
        # Never block the application because an external legal source is unavailable.
        db.session.rollback()

@app.before_request
def automatic_legal_source_check():
    if request.endpoint not in ("static", "health", "login") and request.method == "GET":
        maybe_auto_check_legal_updates()

def get_rule_value(code, default):
    r = LegalRule.query.filter_by(code=code, active=True).first()
    return float(r.value) if r and r.value is not None else default


def add_alert(alert_type, severity, title, message, legal_basis="", supplier_id=None, contract_id=None, procedure_id=None, framework_agreement_id=None):
    existing = ComplianceAlert.query.filter_by(alert_type=alert_type, contract_id=contract_id,
                                                procedure_id=procedure_id, supplier_id=supplier_id,
                                                framework_agreement_id=framework_agreement_id,
                                                resolved=False).first()
    if not existing:
        db.session.add(ComplianceAlert(alert_type=alert_type, severity=severity, title=title,
                                       message=message, legal_basis=legal_basis, supplier_id=supplier_id,
                                       contract_id=contract_id, procedure_id=procedure_id,
                                       framework_agreement_id=framework_agreement_id))


def run_compliance_checks():
    """Rebuild the actionable compliance state without duplicating open alerts.

    Financial-limit checks are data-driven: 90% is a preventive warning and
    100% or more is a critical exception. The check deliberately preserves
    execution percentages above 100% so overruns remain visible.
    """
    today = date.today()
    # Framework-agreement financial controls.
    for fa in FrameworkAgreement.query.all():
        if fa.status == "Em vigor" and fa.end_date and fa.end_date < today:
            add_alert("AQ_EXPIRADO", "CRITICO", "Acordo-Quadro expirado",
                      f"O Acordo-Quadro {fa.code} terminou em {fa.end_date.strftime('%d/%m/%Y')} e continua marcado como em vigor.",
                      "Gestão de contratação", framework_agreement_id=fa.id)
        elif fa.status == "Em vigor" and fa.end_date:
            fa_days = (fa.end_date - today).days
            if fa_days <= 30:
                add_alert("AQ_30_DIAS", "ALERTA", "Acordo-Quadro próximo do vencimento",
                          f"O Acordo-Quadro {fa.code} vence em {fa_days} dia(s).",
                          "Gestão de contratação", framework_agreement_id=fa.id)
        limit = money(fa.estimated_value)
        invoice_filter = or_(
            SupplierInvoice.framework_agreement_id == fa.id,
            SupplierInvoice.contract.has(Contract.framework_agreement_id == fa.id)
        )
        payment_filter = or_(
            SupplierPayment.framework_agreement_id == fa.id,
            SupplierPayment.contract.has(Contract.framework_agreement_id == fa.id)
        )
        invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(invoice_filter).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(payment_filter).scalar())
        execution = (invoiced / limit * 100) if limit else 0
        if limit and execution >= 100:
            excess = invoiced - limit
            add_alert("AQ_LIMITE_ULTRAPASSADO", "CRITICO", "Acordo-Quadro acima do limite",
                      f"O Acordo-Quadro {fa.code} tem faturação de Kz {invoiced:,.2f}, acima do limite de Kz {limit:,.2f} em Kz {excess:,.2f}. Execução: {execution:.2f}%.",
                      "Controlo financeiro do Acordo-Quadro", framework_agreement_id=fa.id)
        elif limit and execution >= 90:
            remaining = max(limit - invoiced, 0)
            add_alert("AQ_PROXIMO_LIMITE", "ALERTA", "Acordo-Quadro próximo do limite",
                      f"O Acordo-Quadro {fa.code} atingiu {execution:.2f}% de execução. Saldo disponível: Kz {remaining:,.2f}.",
                      "Controlo financeiro do Acordo-Quadro", framework_agreement_id=fa.id)
        if limit and paid > invoiced:
            add_alert("AQ_PAGAMENTO_ACIMA_FATURACAO", "CRITICO", "Pagamentos acima da faturação do Acordo-Quadro",
                      f"O Acordo-Quadro {fa.code} possui pagamentos de Kz {paid:,.2f}, superiores à faturação de Kz {invoiced:,.2f}.",
                      "Controlo financeiro", framework_agreement_id=fa.id)

        # If supplier-level allocations exist, their sum must not exceed the AQ limit.
        allocated = money(db.session.execute(text("SELECT COALESCE(SUM(allocated_value),0) FROM framework_supplier WHERE framework_id=:fid"), {"fid": fa.id}).scalar())
        if limit and allocated > limit:
            add_alert("AQ_ALOCACAO_ACIMA_LIMITE", "CRITICO", "Alocação dos fornecedores acima do limite do Acordo-Quadro",
                      f"As alocações dos fornecedores no Acordo-Quadro {fa.code} totalizam Kz {allocated:,.2f}, acima do limite global de Kz {limit:,.2f}.",
                      "Controlo de limites do Acordo-Quadro", framework_agreement_id=fa.id)

    # Contract financial and expiration controls.
    for c in Contract.query.all():
        days = (c.end_date - today).days
        if c.status == "Em vigor" and days < 0:
            add_alert("CONTRATO_EXPIRADO", "CRITICO", "Contrato expirado",
                      f"O contrato {c.number} terminou em {c.end_date.strftime('%d/%m/%Y')} e continua marcado como em vigor.",
                      "Gestão contratual / DP 74/26 — prorrogações devem observar limites legais.", c.supplier_id, c.id)
        elif c.status == "Em vigor" and days <= 7:
            add_alert("CONTRATO_7_DIAS", "CRITICO", "Contrato vence em breve",
                      f"O contrato {c.number} vence em {days} dia(s). Inicie a regularização/novo procedimento.",
                      "Gestão contratual", c.supplier_id, c.id)
        elif c.status == "Em vigor" and days <= 30:
            add_alert("CONTRATO_30_DIAS", "ALERTA", "Contrato vence em 30 dias",
                      f"O contrato {c.number} vence em {days} dia(s).", "Gestão contratual", c.supplier_id, c.id)
        elif c.status == "Em vigor" and days <= 60:
            add_alert("CONTRATO_60_DIAS", "INFO", "Contrato aproxima-se do vencimento",
                      f"O contrato {c.number} vence em {days} dia(s).", "Gestão contratual", c.supplier_id, c.id)

        total = money(c.current_value)
        invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(SupplierInvoice.contract_id == c.id).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.contract_id == c.id).scalar())
        execution = (invoiced / total * 100) if total else 0
        if total and execution >= 100:
            excess = invoiced - total
            add_alert("CONTRATO_LIMITE_ULTRAPASSADO", "CRITICO", "Contrato acima do valor contratado",
                      f"O contrato {c.number} tem faturação de Kz {invoiced:,.2f}, acima do valor actual de Kz {total:,.2f} em Kz {excess:,.2f}. Execução: {execution:.2f}%.",
                      "Controlo financeiro do contrato", c.supplier_id, c.id)
        elif total and execution >= 90:
            add_alert("CONTRATO_PROXIMO_LIMITE", "ALERTA", "Contrato próximo do limite",
                      f"O contrato {c.number} atingiu {execution:.2f}% de execução. Saldo disponível: Kz {max(total-invoiced,0):,.2f}.",
                      "Controlo financeiro do contrato", c.supplier_id, c.id)
        if paid > invoiced:
            add_alert("PAGAMENTO_ACIMA_FATURA_CONTRATO", "CRITICO", "Pagamentos acima da faturação do contrato",
                      f"O contrato {c.number} possui pagamentos de Kz {paid:,.2f}, superiores à faturação de Kz {invoiced:,.2f}.",
                      "Controlo financeiro", c.supplier_id, c.id)

        if c.amendments_percent and float(c.amendments_percent) > get_rule_value("REOGE_AMEND", 15):
            add_alert("ADENDA_EXCESSIVA", "CRITICO", "Adendas acima do limite parametrizado",
                      f"O contrato {c.number} acumula {c.amendments_percent}% em adendas, acima do limite de {get_rule_value('REOGE_AMEND',15):g}%.",
                      "DP 74/26, Art. 10.º", c.supplier_id, c.id)
        if c.advance_percent:
            limit_adv = get_rule_value("REOGE_ADV_WORKS", 15) if c.contract_type == "Empreitada" else get_rule_value("REOGE_ADV_GOODS", 50)
            if float(c.advance_percent) > limit_adv:
                add_alert("ADIANTAMENTO_EXCESSIVO", "CRITICO", "Adiantamento acima do limite parametrizado",
                          f"O contrato {c.number} tem adiantamento de {c.advance_percent}%, acima do limite base de {limit_adv:g}%.",
                          "DP 74/26, Art. 10.º", c.supplier_id, c.id)
        if not c.cabimentado:
            add_alert("SEM_CABIMENTACAO", "CRITICO", "Contrato sem cabimentação registada",
                      f"O contrato {c.number} está marcado sem cabimentação. Não deve avançar a execução sem a condição orçamental aplicável.",
                      "Lei 41/20, Art. 32.º; DP 74/26, Art. 10.º", c.supplier_id, c.id)
        if c.contract_type in ("Bens", "Serviços") and (c.end_date - c.start_date).days > 48*31:
            add_alert("PRAZO_CONTINUO", "CRITICO", "Prazo superior ao limite de 48 meses",
                      f"O contrato {c.number} ultrapassa aproximadamente 48 meses de vigência.",
                      "DP 74/26, Art. 10.º", c.supplier_id, c.id)
        if float(c.current_value or 0) >= get_rule_value("REOGE_HIGH_VALUE", 182000000) and c.contract_type in ("Bens", "Serviços"):
            add_alert("ALTO_VALOR", "ALERTA", "Contrato de alto valor",
                      f"O contrato {c.number} ultrapassa Kz {get_rule_value('REOGE_HIGH_VALUE',182000000):,.0f}. Rever diligências de beneficiário efetivo e documentação financeira quando legalmente solicitadas.",
                      "DP 74/26, Art. 10.º", c.supplier_id, c.id)

    # Invoice/payment consistency checks.
    for inv in SupplierInvoice.query.all():
        payments_total = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.invoice_id == inv.id).scalar())
        if payments_total > money(inv.total):
            add_alert("PAGAMENTO_ACIMA_FATURA", "CRITICO", "Pagamento superior ao valor da fatura",
                      f"A fatura {inv.number} tem pagamentos de Kz {payments_total:,.2f}, superiores ao total de Kz {money(inv.total):,.2f}.",
                      "Controlo financeiro", inv.supplier_id, inv.contract_id)
        duplicate = SupplierInvoice.query.filter(SupplierInvoice.supplier_id == inv.supplier_id, SupplierInvoice.number == inv.number, SupplierInvoice.id != inv.id).first()
        if duplicate:
            add_alert("FATURA_DUPLICADA", "CRITICO", "Fatura potencialmente duplicada",
                      f"A fatura {inv.number} do fornecedor {inv.supplier.name} aparece mais de uma vez.",
                      "Controlo de documentos financeiros", inv.supplier_id, inv.contract_id)

    # Procedure checks.
    level1 = get_rule_value("LCP_SIMPLIFIED", 18000000)
    level5 = get_rule_value("LCP_INVITATION", 182000000)
    for p in ProcurementProcedure.query.all():
        v = float(p.estimated_value or 0)
        if not p.budgeted or not p.cabimentado:
            add_alert("PROCEDIMENTO_SEM_ORCAMENTO", "CRITICO", "Procedimento sem cobertura/cabimentação registada",
                      f"O procedimento {p.code} não tem orçamento/cabimentação marcados como regulares.",
                      "Lei 41/20, Art. 32.º; DP 74/26, Art. 10.º", p.supplier_id, None, p.id)
        if p.contract_category == "Concessão" and p.procedure_type not in ("Concurso Público", "Concurso Limitado por Prévia Qualificação"):
            add_alert("PROCEDIMENTO_INADEQUADO", "CRITICO", "Procedimento incompatível com concessão",
                      f"O procedimento {p.code} usa {p.procedure_type} para concessão.", "Lei 41/20, Art. 24.º, n.º 5", p.supplier_id, None, p.id)
        if p.procedure_type == "Contratação Simplificada" and v > level1:
            add_alert("SIMPLIFICADA_ACIMA_LIMITE", "CRITICO", "Contratação Simplificada acima do limite",
                      f"O procedimento {p.code} tem valor estimado de Kz {v:,.2f}, acima do Nível 1 parametrizado (Kz {level1:,.2f}). Só deve prosseguir se existir fundamento material legal aplicável.",
                      "Lei 41/20, Art. 24.º e 27.º–30.º", p.supplier_id, None, p.id)
        if p.procedure_type == "Concurso Limitado por Convite" and v >= level5:
            add_alert("CONVITE_ACIMA_LIMITE", "CRITICO", "Concurso Limitado por Convite fora do limite",
                      f"O procedimento {p.code} tem valor estimado de Kz {v:,.2f}, não inferior ao limite parametrizado do Nível 5 (Kz {level5:,.2f}).", "Lei 41/20, Art. 24.º", p.supplier_id, None, p.id)
        if p.procedure_type in ("Contratação Simplificada", "Contratação Emergencial") and not p.justification:
            add_alert("SEM_FUNDAMENTACAO", "ALERTA", "Procedimento excepcional sem fundamentação registada",
                      f"O procedimento {p.code} exige revisão da fundamentação e do critério material/emergencial, conforme aplicável.", "Lei 41/20, Art. 26.º–31.º", p.supplier_id, None, p.id)
        if not p.portal_registered:
            add_alert("PORTAL_NAO_REGISTADO", "ALERTA", "Registo no Portal não confirmado",
                      f"O procedimento {p.code} está marcado sem registo confirmado no Portal da Contratação Pública.", "Lei 41/20, Art. 12.º e regras do procedimento", p.supplier_id, None, p.id)

    db.session.commit()

# -----------------------------------------------------------------------------
# Backup / recovery / audit (administrator only)
# -----------------------------------------------------------------------------
BACKUP_MODELS = [User, Client, Invoice, Payment, Supplier, ProcurementProcedure,
                 Contract, SupplierInvoice, SupplierPayment, LegalRule, ComplianceAlert, LegalDocument, LegalVersion, LegalUpdateCheck]

def audit(action, model=None, record_id=None, details=""):
    try:
        db.session.add(AuditLog(user_id=session.get("uid"), action=action, model=model,
                                record_id=record_id, details=details[:4000],
                                ip_address=request.headers.get("X-Forwarded-For", request.remote_addr)))
        db.session.commit()
    except Exception:
        db.session.rollback()

def json_value(v):
    if isinstance(v, (date, datetime)): return v.isoformat()
    if isinstance(v, Decimal): return str(v)
    return v

def make_backup_payload():
    payload={"format":"ChivuGest Backup v1", "created_at":datetime.utcnow().isoformat()+"Z", "tables":{}}
    for cls in BACKUP_MODELS:
        rows=[]
        for obj in cls.query.order_by(cls.id).all():
            rows.append({c.name: json_value(getattr(obj,c.name)) for c in inspect(cls).columns})
        payload["tables"][cls.__tablename__]=rows
    return payload

def restore_value(col, raw):
    if raw is None: return None
    n=col.type.__class__.__name__
    if n=="Date": return parse_date(raw, None)
    if n in ("DateTime",): return datetime.fromisoformat(raw.replace("Z","+00:00")).replace(tzinfo=None)
    if n in ("Numeric","Float","REAL"): return Decimal(str(raw))
    if n=="Integer": return int(raw)
    if n=="Boolean": return bool(raw)
    return raw

def restore_payload(payload):
    if payload.get("format") != "ChivuGest Backup v1": raise ValueError("Formato de backup inválido.")
    table_to_model={m.__tablename__:m for m in BACKUP_MODELS}
    # Delete dependents first; audit and backup history remain untouched.
    delete_order=[SupplierPayment, SupplierInvoice, Contract, ProcurementProcedure, ComplianceAlert,
                  Payment, Invoice, LegalRule, LegalDocument, Supplier, Client, User]
    for cls in delete_order:
        cls.query.delete(synchronize_session=False)
    db.session.flush()
    # Insert parents before dependents.
    insert_order=[User, Client, Supplier, LegalRule, LegalDocument, ProcurementProcedure, Contract,
                  Invoice, Payment, SupplierInvoice, SupplierPayment, ComplianceAlert]
    for cls in insert_order:
        rows=payload.get("tables",{}).get(cls.__tablename__,[])
        cols={c.name:c for c in inspect(cls).columns}
        for row in rows:
            obj=cls()
            for name, raw in row.items():
                if name in cols: setattr(obj,name,restore_value(cols[name],raw))
            db.session.add(obj)
        db.session.flush()
    db.session.commit()

@app.route("/admin/backup", methods=["GET","POST"])
@login_required
@admin_required
def backup_center():
    if request.method=="POST" and request.form.get("action")=="create":
        payload=make_backup_payload()
        raw=json.dumps(payload, ensure_ascii=False, separators=(",",":"), default=json_value).encode("utf-8")
        digest=hashlib.sha256(raw).hexdigest()
        code="BKP-"+datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+secrets.token_hex(3).upper()
        fname=code+".json"
        rec=BackupRecord(code=code, created_by=session.get("uid"), file_name=fname, sha256=digest, size_bytes=len(raw))
        db.session.add(rec); db.session.commit(); audit("BACKUP_CREATE","BackupRecord",rec.id,fname)
        return Response(raw,mimetype="application/json; charset=utf-8",headers={"Content-Disposition":f"attachment; filename={fname}","X-ChivuGest-Backup-SHA256":digest})
    return render_template("backup.html", backups=BackupRecord.query.order_by(BackupRecord.created_at.desc()).limit(50).all(), audits=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(30).all())

@app.route("/admin/backup/restore", methods=["POST"])
@login_required
@admin_required
def backup_restore():
    f=request.files.get("backup_file")
    if not f or not f.filename.lower().endswith(".json"):
        flash("Selecione um ficheiro de backup JSON válido."); return redirect(url_for("backup_center"))
    if request.form.get("confirmation")!="RESTAURAR":
        flash("Para restaurar, escreva exatamente RESTAURAR."); return redirect(url_for("backup_center"))
    try:
        payload=json.load(f.stream)
        restore_payload(payload)
        audit("BACKUP_RESTORE","Backup",None,f"Restauro a partir de {f.filename}")
        flash("Backup restaurado com sucesso. Verifique os dados e faça novo login se necessário.")
    except Exception as e:
        db.session.rollback(); flash("Falha ao restaurar o backup: "+str(e))
    return redirect(url_for("backup_center"))

@app.route("/admin/audit")
@login_required
@admin_required
def audit_center():
    return render_template("audit.html", rows=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(300).all())

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if u and u.active and check_password_hash(u.password_hash, request.form.get("password", "")):
            session.update(uid=u.id, name=u.name, role=u.role)
            return redirect(url_for("dashboard"))
        flash("Utilizador ou palavra-passe inválidos.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    # Refresh compliance first; KPI counters must reflect alerts generated by
    # the same request (the previous version counted before running checks).
    run_compliance_checks()
    total_invoices = db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).scalar() or 0
    total_paid = db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).scalar() or 0
    payable = max(float(total_invoices) - float(total_paid), 0)
    overdue = db.session.query(func.coalesce(func.sum(SupplierInvoice.total - SupplierInvoice.paid), 0)).filter(
        SupplierInvoice.due_date < date.today(), SupplierInvoice.total > SupplierInvoice.paid).scalar() or 0
    contracts_active = Contract.query.filter(Contract.status == "Em vigor", Contract.end_date >= date.today()).count()
    framework_agreements_active = FrameworkAgreement.query.filter(FrameworkAgreement.status == "Em vigor", or_(FrameworkAgreement.end_date == None, FrameworkAgreement.end_date >= date.today())).count()
    expiring = Contract.query.filter(Contract.status == "Em vigor", Contract.end_date <= date.today()+timedelta(days=60), Contract.end_date >= date.today()).count()
    critical_alerts = ComplianceAlert.query.filter_by(resolved=False, severity="CRITICO").count()
    alert_count = ComplianceAlert.query.filter_by(resolved=False).count()
    regularization_count = ComplianceAlert.query.filter(ComplianceAlert.resolved == False, ComplianceAlert.severity.in_(["CRITICO", "ALERTA"])).count()
    suppliers = Supplier.query.count()
    recent_payments = SupplierPayment.query.order_by(SupplierPayment.id.desc()).limit(8).all()
    recent_contracts = Contract.query.filter_by(status="Em vigor").order_by(Contract.end_date).limit(6).all()

    contract_execution = []
    for c in Contract.query.order_by(Contract.end_date).all():
        total_value = money(c.current_value)
        executed = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(SupplierInvoice.contract_id == c.id).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.contract_id == c.id).scalar())
        balance = total_value - executed
        remaining = max(balance, 0)
        excess = max(-balance, 0)
        execution_pct = (executed / total_value * 100) if total_value else 0
        contract_execution.append({"obj": c, "total": total_value, "executed": executed, "paid": paid,
                                   "remaining": remaining, "excess": excess, "execution": execution_pct})

    framework_execution = []
    for fa in FrameworkAgreement.query.order_by(FrameworkAgreement.code).all():
        total_value = money(fa.estimated_value)
        invoice_filter = or_(SupplierInvoice.framework_agreement_id == fa.id,
                             SupplierInvoice.contract.has(Contract.framework_agreement_id == fa.id))
        payment_filter = or_(SupplierPayment.framework_agreement_id == fa.id,
                             SupplierPayment.contract.has(Contract.framework_agreement_id == fa.id))
        executed = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(invoice_filter).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(payment_filter).scalar())
        balance = total_value - executed
        remaining = max(balance, 0)
        excess = max(-balance, 0)
        execution_pct = (executed / total_value * 100) if total_value else 0
        framework_execution.append({"obj": fa, "total": total_value, "executed": executed, "paid": paid,
                                    "remaining": remaining, "excess": excess, "execution": execution_pct})

    company_analysis = []
    for s in Supplier.query.order_by(Supplier.name).all():
        contract_value = money(db.session.query(func.coalesce(func.sum(Contract.current_value), 0)).filter(Contract.supplier_id == s.id).scalar())
        invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(SupplierInvoice.supplier_id == s.id).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.supplier_id == s.id).scalar())
        fa_count = db.session.query(func.count(func.distinct(framework_supplier.c.framework_id))).filter(framework_supplier.c.supplier_id == s.id).scalar() or 0
        contract_count = Contract.query.filter_by(supplier_id=s.id).count()
        execution_pct = (invoiced / contract_value * 100) if contract_value else None
        company_analysis.append({"obj": s, "framework_count": int(fa_count), "contract_count": contract_count, "contract_value": contract_value,
                                 "invoiced": invoiced, "paid": paid, "payable": max(invoiced-paid,0), "execution": execution_pct})

    monthly = db.session.query(func.extract("year", SupplierPayment.date).label("y"), func.extract("month", SupplierPayment.date).label("m"), func.sum(SupplierPayment.amount).label("v")).group_by("y","m").order_by("y","m").all()
    months = [{"label": f"{int(r.y):04d}-{int(r.m):02d}", "value": float(r.v or 0)} for r in monthly]
    maxv = max([m["value"] for m in months], default=0)
    for m in months: m["height"] = 20 + (m["value"]/(maxv or 1))*180
    latest_backup = BackupRecord.query.order_by(BackupRecord.created_at.desc()).first()
    return render_template("dashboard.html", total_invoices=total_invoices, total_paid=total_paid, payable=payable,
                           overdue=overdue, contracts_active=contracts_active, framework_agreements_active=framework_agreements_active, expiring=expiring,
                           critical_alerts=critical_alerts, alert_count=alert_count, regularization_count=regularization_count, suppliers=suppliers,
                           recent_payments=recent_payments, recent_contracts=recent_contracts, contract_execution=contract_execution, framework_execution=framework_execution,
                           company_analysis=company_analysis, months=months, latest_backup=latest_backup)

# -----------------------------------------------------------------------------
# Suppliers
# -----------------------------------------------------------------------------
@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    if request.method == "POST":
        try:
            s = Supplier(name=request.form["name"].strip(), nif=request.form.get("nif"), phone=request.form.get("phone"),
                         email=request.form.get("email"), address=request.form.get("address"), category=request.form.get("category"),
                         contracting_type="Não aplicável",
                         notes=request.form.get("notes"))
            db.session.add(s); db.session.commit(); flash("Fornecedor criado. Pode ser associado a vários procedimentos e Acordos-Quadro.")
        except Exception as e:
            db.session.rollback(); flash("Não foi possível criar o fornecedor: "+str(e))
    return render_template("suppliers.html", rows=Supplier.query.order_by(Supplier.name).all())

# -----------------------------------------------------------------------------
# Supplier/company analysis
# -----------------------------------------------------------------------------
@app.route("/supplier-analysis")
@login_required
def supplier_analysis():
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    selected_id = request.args.get("supplier_id", type=int)
    selected = db.session.get(Supplier, selected_id) if selected_id else None
    companies = []
    for s in suppliers_list:
        contract_count = Contract.query.filter_by(supplier_id=s.id).count()
        active_contract_count = Contract.query.filter_by(supplier_id=s.id, status="Em vigor").count()
        contract_value = money(db.session.query(func.coalesce(func.sum(Contract.current_value), 0)).filter(Contract.supplier_id == s.id).scalar())
        invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(SupplierInvoice.supplier_id == s.id).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.supplier_id == s.id).scalar())
        payable = max(invoiced - paid, 0)
        execution = (invoiced / contract_value * 100) if contract_value else None
        fa_count = db.session.query(func.count(func.distinct(framework_supplier.c.framework_id))).filter(framework_supplier.c.supplier_id == s.id).scalar() or 0
        companies.append({"obj": s, "framework_count": int(fa_count), "contract_count": contract_count, "active_contract_count": active_contract_count,
                          "contract_value": contract_value, "invoiced": invoiced, "paid": paid, "payable": payable, "execution": execution})
    selected_detail = None
    if selected:
        companies = [c for c in companies if c["obj"].id == selected.id]
        # Complete analytical profile for the selected company.
        detail_frameworks = []
        for fa in selected.framework_agreements:
            fa_invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(
                SupplierInvoice.supplier_id == selected.id, SupplierInvoice.framework_agreement_id == fa.id).scalar())
            fa_paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(
                SupplierPayment.supplier_id == selected.id, SupplierPayment.framework_agreement_id == fa.id).scalar())
            allocation = money(db.session.execute(text("SELECT COALESCE(allocated_value,0) FROM framework_supplier WHERE framework_id=:fid AND supplier_id=:sid"), {"fid": fa.id, "sid": selected.id}).scalar())
            fa_total = allocation
            fa_remaining = max(fa_total - fa_invoiced, 0)
            fa_excess = max(fa_invoiced - fa_total, 0)
            fa_exec = (fa_invoiced / fa_total * 100) if fa_total else None
            detail_frameworks.append({"obj": fa, "total": fa_total, "invoiced": fa_invoiced, "paid": fa_paid,
                                     "remaining": fa_remaining, "excess": fa_excess, "execution": fa_exec})

        detail_contracts = []
        for c in Contract.query.filter_by(supplier_id=selected.id).order_by(Contract.end_date, Contract.number).all():
            c_total = money(c.current_value)
            c_invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total), 0)).filter(SupplierInvoice.contract_id == c.id).scalar())
            c_paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.contract_id == c.id).scalar())
            c_remaining = max(c_total - c_invoiced, 0)
            c_excess = max(c_invoiced - c_total, 0)
            c_exec = (c_invoiced / c_total * 100) if c_total else None
            detail_contracts.append({"obj": c, "total": c_total, "invoiced": c_invoiced, "paid": c_paid,
                                     "remaining": c_remaining, "excess": c_excess, "execution": c_exec})

        detail_invoices = SupplierInvoice.query.filter_by(supplier_id=selected.id).order_by(SupplierInvoice.issue_date.desc(), SupplierInvoice.id.desc()).all()
        detail_payments = SupplierPayment.query.filter_by(supplier_id=selected.id).order_by(SupplierPayment.date.desc(), SupplierPayment.id.desc()).all()
        selected_detail = {
            "supplier": selected,
            "frameworks": detail_frameworks,
            "contracts": detail_contracts,
            "invoices": detail_invoices,
            "payments": detail_payments,
            "invoice_total": money(sum((float(i.total or 0) for i in detail_invoices), 0)),
            "invoice_paid": money(sum((float(i.paid or 0) for i in detail_invoices), 0)),
            "payment_total": money(sum((float(x.amount or 0) for x in detail_payments), 0)),
        }
        selected_detail["invoice_balance"] = max(selected_detail["invoice_total"] - selected_detail["payment_total"], 0)
    totals = {
        "companies": len(companies),
        "contracts": sum(c["contract_count"] for c in companies),
        "contract_value": sum(c["contract_value"] for c in companies),
        "invoiced": sum(c["invoiced"] for c in companies),
        "paid": sum(c["paid"] for c in companies),
    }
    totals["payable"] = max(totals["invoiced"] - totals["paid"], 0)
    totals["execution"] = (totals["invoiced"] / totals["contract_value"] * 100) if totals["contract_value"] else None
    return render_template("supplier_analysis.html", companies=companies, suppliers=suppliers_list, selected=selected, totals=totals, selected_detail=selected_detail)

# -----------------------------------------------------------------------------
# Supplier invoices and payments
# -----------------------------------------------------------------------------
@app.route("/invoices", methods=["GET", "POST"])
@login_required
def supplier_invoices():
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    contracts = Contract.query.filter_by(status="Em vigor").order_by(Contract.number).all()
    framework_agreements = FrameworkAgreement.query.order_by(FrameworkAgreement.code).all()
    if request.method == "POST":
        try:
            supplier = db.session.get(Supplier, int(request.form["supplier_id"]))
            if not supplier:
                raise ValueError("Fornecedor inválido.")
            total = num(request.form["total"])
            if total <= 0:
                raise ValueError("O valor da fatura deve ser superior a zero.")
            duplicate_invoice = SupplierInvoice.query.filter_by(supplier_id=int(request.form["supplier_id"]), number=request.form["number"].strip()).first()
            if duplicate_invoice:
                raise ValueError("Já existe uma fatura com este número para o fornecedor seleccionado.")

            contract = db.session.get(Contract, int(request.form["contract_id"])) if request.form.get("contract_id") else None
            framework_id = int(request.form["framework_agreement_id"]) if request.form.get("framework_agreement_id") else None
            framework = db.session.get(FrameworkAgreement, framework_id) if framework_id else None

            # Contract is the strongest link: inherit its supplier and Acordo-Quadro.
            if contract:
                if contract.supplier_id != supplier.id:
                    raise ValueError("O fornecedor da fatura não corresponde ao fornecedor do contrato seleccionado.")
                contract_framework_id = contract.framework_agreement_id
                if framework_id and framework_id != contract_framework_id:
                    raise ValueError("O Acordo-Quadro seleccionado não corresponde ao contrato.")
                framework_id = contract_framework_id
                framework = contract.framework_agreement

            if framework:
                participating_supplier_ids = {s.id for s in framework.suppliers.all()}
                if supplier.id not in participating_supplier_ids:
                    raise ValueError("O fornecedor seleccionado não participa no Acordo-Quadro indicado.")

            inv = SupplierInvoice(
                number=request.form["number"].strip(),
                supplier_id=supplier.id,
                contract_id=contract.id if contract else None,
                framework_agreement_id=framework_id,
                issue_date=parse_date(request.form.get("issue_date")),
                due_date=None, subtotal=0, vat=0, total=total, paid=0, currency="AOA",
                status="Pendente", source_filename=request.form.get("source_filename"))
            db.session.add(inv); db.session.commit()
            flash("Fatura registada. A relação com o Acordo-Quadro/contrato foi guardada e será herdada nos pagamentos.")
        except Exception as e:
            db.session.rollback(); flash("Erro ao registar fatura: "+str(e))
    rows = SupplierInvoice.query.order_by(SupplierInvoice.id.desc()).all()
    return render_template("supplier_invoices.html", rows=rows, suppliers=suppliers_list, contracts=contracts, framework_agreements=framework_agreements)

@app.route("/payments", methods=["GET", "POST"])
@login_required
def supplier_payments():
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    invoices = SupplierInvoice.query.order_by(SupplierInvoice.id.desc()).all()
    contracts = Contract.query.filter_by(status="Em vigor").all()
    framework_agreements = FrameworkAgreement.query.order_by(FrameworkAgreement.code).all()
    if request.method == "POST":
        try:
            amount = num(request.form["amount"])
            if amount <= 0:
                raise ValueError("O valor do pagamento deve ser superior a zero.")
            inv = db.session.get(SupplierInvoice, int(request.form["invoice_id"])) if request.form.get("invoice_id") else None
            supplier_id = int(request.form["supplier_id"]) if request.form.get("supplier_id") else None
            contract = db.session.get(Contract, int(request.form["contract_id"])) if request.form.get("contract_id") else None
            framework_id = int(request.form["framework_agreement_id"]) if request.form.get("framework_agreement_id") else None
            framework = db.session.get(FrameworkAgreement, framework_id) if framework_id else None

            # A selected invoice is the source of truth: supplier, contract and Acordo-Quadro
            # are inherited automatically, preventing inconsistent manual combinations.
            if inv:
                supplier_id = inv.supplier_id
                if inv.contract_id:
                    contract = inv.contract
                framework_id = inv.framework_agreement_id
                framework = inv.framework_agreement
            elif contract:
                supplier_id = contract.supplier_id
                framework_id = contract.framework_agreement_id
                framework = contract.framework_agreement

            if not supplier_id:
                raise ValueError("Seleccione o fornecedor ou uma fatura/contrato que permita identificá-lo.")
            supplier = db.session.get(Supplier, supplier_id)
            if not supplier:
                raise ValueError("Fornecedor inválido.")
            if framework:
                if supplier.id not in {s.id for s in framework.suppliers.all()}:
                    raise ValueError("O fornecedor seleccionado não participa no Acordo-Quadro indicado.")
            if contract and contract.supplier_id != supplier.id:
                raise ValueError("O contrato seleccionado não pertence ao fornecedor indicado.")
            if contract and framework_id and contract.framework_agreement_id != framework_id:
                raise ValueError("O contrato e o Acordo-Quadro seleccionados não correspondem entre si.")

            if inv:
                current_paid = money(inv.paid)
                if current_paid + amount > money(inv.total):
                    raise ValueError(f"O pagamento de Kz {amount:,.2f} ultrapassa o saldo disponível da fatura (Kz {max(money(inv.total)-current_paid,0):,.2f}).")
                inv.paid = current_paid + amount
                inv.status = "Paga" if inv.paid >= inv.total else "Parcial"
            p = SupplierPayment(receipt=request.form["receipt"], supplier_id=supplier_id,
                                invoice_id=inv.id if inv else None,
                                contract_id=contract.id if contract else None,
                                framework_agreement_id=framework_id,
                                date=parse_date(request.form.get("date")), method=request.form["method"], amount=amount,
                                reference=request.form.get("reference"), notes=request.form.get("notes"))
            db.session.add(p); db.session.commit(); flash("Pagamento registado com rastreabilidade ao Acordo-Quadro/contrato.")
        except Exception as e:
            db.session.rollback(); flash("Erro no pagamento: "+str(e))
    return render_template("supplier_payments.html", rows=SupplierPayment.query.order_by(SupplierPayment.id.desc()).all(), orders=PaymentOrder.query.order_by(PaymentOrder.id.desc()).limit(200).all(), suppliers=suppliers_list, invoices=invoices, contracts=contracts, framework_agreements=framework_agreements)

@app.route("/payments/import-documents", methods=["POST"])
@login_required
def import_payment_documents():
    f=request.files.get("file")
    source_type=request.form.get("source_type","DocFonte")
    if not f or not f.filename:
        flash("Selecione um ficheiro para importar."); return redirect(url_for("supplier_payments"))
    try:
        filename=(f.filename or "").lower()
        created=0
        if filename.endswith((".csv", ".xlsx")):
            rows=uploaded_rows(f)
            for r in rows:
                parsed={
                    "os_number": str(row_value(r,"ordem_saque","ordem_de_saque","os","numero_os","n_os","ordem","numero_ordem","referencia")).strip(),
                    "supplier": str(row_value(r,"fornecedor","supplier","emitente","beneficiario","beneficiario")).strip(),
                    "nif": str(row_value(r,"nif","nuit","tax_id")).strip(),
                    "invoice_number": str(row_value(r,"fatura","factura","numero_fatura","invoice_number","documento")).strip(),
                    "date": row_value(r,"data","data_emissao","issue_date","data_os"),
                    "amount": num(row_value(r,"valor","valor_os","montante","amount","total")),
                    "status": str(row_value(r,"situacao","situacao_os","status","estado") or "Pendente").strip(),
                    "bank_reference": str(row_value(r,"referencia_bancaria","referencia_banco","bank_reference","referencia")).strip(),
                }
                parsed["date_parsed"]=parse_date(parsed.get("date"),None); parsed["filename"]=f.filename
                parsed["confidence"]=min(100, sum(bool(parsed.get(k)) for k in ("os_number","supplier","invoice_number","date","amount"))*20 + (10 if parsed.get("nif") else 0))
                if not parsed["os_number"]: continue
                # Stable row hash avoids duplicate imports while preserving one hash per OS row.
                parsed["hash"]=hashlib.sha256((hashlib.sha256(f.getvalue()).hexdigest()+json.dumps(parsed,sort_keys=True,default=str)).encode()).hexdigest()
                if PaymentOrder.query.filter_by(source_hash=parsed["hash"]).first(): continue
                supplier,invoice,contract,recon_status,recon_notes=match_payment_order(parsed)
                if not supplier:
                    sname=(parsed.get("supplier") or "Fornecedor a identificar").strip()
                    supplier=Supplier.query.filter_by(name=sname).first()
                    if not supplier:
                        supplier=Supplier(name=sname,nif=parsed.get("nif") or None,contracting_type="Outro / Regime especial")
                        db.session.add(supplier); db.session.flush()
                doc=SourceDocument(document_type=source_type,document_number=parsed["os_number"],supplier_id=supplier.id,source_filename=f.filename,source_hash=parsed["hash"],issue_date=parsed["date_parsed"],amount=parsed["amount"],extracted_data=json.dumps(parsed,ensure_ascii=False),import_confidence=parsed["confidence"])
                osr=PaymentOrder(os_number=parsed["os_number"],supplier_id=supplier.id,invoice_id=invoice.id if invoice else None,contract_id=contract.id if contract else None,framework_agreement_id=(contract.framework_agreement_id if contract else (invoice.framework_agreement_id if invoice else None)),issue_date=parsed["date_parsed"],amount=parsed["amount"],status=normalize_os_status(parsed["status"]),bank_reference=parsed["bank_reference"],source_type=source_type,source_filename=f.filename,source_hash=parsed["hash"],extracted_data=json.dumps(parsed,ensure_ascii=False),reconciliation_status=recon_status,reconciliation_notes=recon_notes)
                db.session.add_all([doc,osr]); created+=1
            db.session.commit()
        else:
            parsed=extract_generic_source_document(f)
            if SourceDocument.query.filter_by(source_hash=parsed["hash"]).first() or PaymentOrder.query.filter_by(source_hash=parsed["hash"]).first():
                raise ValueError("Este documento já foi importado anteriormente.")
            supplier,invoice,contract,recon_status,recon_notes=match_payment_order(parsed)
            if not supplier:
                sname=(parsed.get("supplier") or "Fornecedor a identificar").strip()
                supplier=Supplier.query.filter_by(name=sname).first()
                if not supplier:
                    supplier=Supplier(name=sname,nif=parsed.get("nif") or None,contracting_type="Outro / Regime especial")
                    db.session.add(supplier); db.session.flush()
            doc=SourceDocument(document_type=source_type,document_number=parsed.get("os_number") or parsed.get("invoice_number") or None,supplier_id=supplier.id,source_filename=parsed["filename"],source_hash=parsed["hash"],issue_date=parsed.get("date_parsed"),amount=parsed.get("amount",0),extracted_data=json.dumps(parsed,ensure_ascii=False),import_confidence=parsed.get("confidence",0))
            osr=PaymentOrder(os_number=parsed.get("os_number") or parsed.get("invoice_number") or "SEM-NUMERO",supplier_id=supplier.id,invoice_id=invoice.id if invoice else None,contract_id=contract.id if contract else None,framework_agreement_id=(contract.framework_agreement_id if contract else (invoice.framework_agreement_id if invoice else None)),issue_date=parsed.get("date_parsed"),amount=parsed.get("amount",0),status=normalize_os_status(parsed.get("status")),bank_reference=parsed.get("bank_reference"),source_type=source_type,source_filename=parsed["filename"],source_hash=parsed["hash"],extracted_data=json.dumps(parsed,ensure_ascii=False),reconciliation_status=recon_status,reconciliation_notes=recon_notes)
            db.session.add_all([doc,osr]); created=1; db.session.commit()
        flash(f"Importação concluída: {created} documento(s)/ordem(ns) de saque. As informações foram cruzadas por fornecedor, NIF, fatura, valor e situação.")
    except Exception as e:
        db.session.rollback(); flash("Erro na importação do documento: "+str(e))
    return redirect(url_for("supplier_payments"))

@app.route("/current")
@login_required
def current_account():
    supplier_id = request.args.get("supplier_id", type=int)
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    inv_q = SupplierInvoice.query.order_by(SupplierInvoice.issue_date, SupplierInvoice.id)
    pay_q = SupplierPayment.query.order_by(SupplierPayment.date, SupplierPayment.id)
    if supplier_id:
        inv_q = inv_q.filter_by(supplier_id=supplier_id); pay_q = pay_q.filter_by(supplier_id=supplier_id)
    entries=[]
    for i in inv_q.all(): entries.append((i.issue_date, i.number, "Fatura", money(i.total), 0, i.supplier.name))
    for p in pay_q.all(): entries.append((p.date, p.receipt, "Pagamento", 0, money(p.amount), p.supplier.name))
    entries.sort(key=lambda x:(x[0],x[1] or "")); bal=0; rows=[]
    for e in entries:
        bal += e[3]-e[4]; rows.append((e,bal))
    return render_template("current.html", rows=rows, suppliers=suppliers_list, supplier_id=supplier_id)

# -----------------------------------------------------------------------------
# Contracts and procurement
# -----------------------------------------------------------------------------
@app.route("/framework-agreements", methods=["GET", "POST"])
@login_required
def framework_agreements():
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    procedures = ["Concurso Limitado por Convite", "Concurso Público", "Contratação Simplificada", "Concurso Limitado por Prévia Qualificação", "Procedimento de Contratação Emergencial"]
    if request.method == "POST":
        try:
            code=request.form["code"].strip()
            if FrameworkAgreement.query.filter_by(code=code).first():
                raise ValueError("Já existe um Acordo-Quadro com este número/código.")
            fa=FrameworkAgreement(
                code=code, object=request.form["object"].strip(),
                procedure_type=request.form.get("procedure_type") or "Concurso Limitado por Convite",
                start_date=parse_date(request.form.get("start_date"), None),
                end_date=parse_date(request.form.get("end_date"), None),
                estimated_value=num(request.form.get("estimated_value")),
                status=request.form.get("status") or "Em vigor",
                legal_basis=request.form.get("legal_basis"), document_ref=request.form.get("document_ref"),
                notes=request.form.get("notes"))
            selected=[]
            for sid in request.form.getlist("supplier_ids"):
                s=db.session.get(Supplier,int(sid))
                if s: selected.append(s)
            if not selected: raise ValueError("Associe pelo menos um fornecedor ao Acordo-Quadro.")
            fa.suppliers.extend(selected)
            db.session.add(fa); db.session.flush()
            for supplier in selected:
                allocation = num(request.form.get(f"supplier_limit_{supplier.id}"))
                db.session.execute(text("UPDATE framework_supplier SET allocated_value=:v WHERE framework_id=:fid AND supplier_id=:sid"), {"v": allocation, "fid": fa.id, "sid": supplier.id})
            db.session.commit()
            flash(f"Acordo-Quadro {fa.code} criado com {len(selected)} fornecedor(es).")
        except Exception as e:
            db.session.rollback(); flash("Erro ao criar Acordo-Quadro: "+str(e))
    rows=FrameworkAgreement.query.order_by(FrameworkAgreement.id.desc()).all()
    return render_template("framework_agreements.html", rows=rows, suppliers=suppliers_list, procedures=procedures)

@app.route("/framework-agreements/<int:fa_id>/edit", methods=["GET", "POST"])
@login_required
def edit_framework_agreement(fa_id):
    fa = db.session.get(FrameworkAgreement, fa_id)
    if not fa:
        flash("Acordo-Quadro não encontrado.")
        return redirect(url_for("framework_agreements"))
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    allocations = {int(r["supplier_id"]): money(r["allocated_value"]) for r in db.session.execute(text("SELECT supplier_id, allocated_value FROM framework_supplier WHERE framework_id=:fid"), {"fid": fa.id}).mappings()}
    if request.method == "POST":
        try:
            code = request.form["code"].strip()
            duplicate = FrameworkAgreement.query.filter(FrameworkAgreement.code == code, FrameworkAgreement.id != fa.id).first()
            if duplicate:
                raise ValueError("Já existe outro Acordo-Quadro com este número/código.")

            selected_ids = {int(sid) for sid in request.form.getlist("supplier_ids") if str(sid).isdigit()}
            if not selected_ids:
                raise ValueError("Associe pelo menos um fornecedor ao Acordo-Quadro.")

            current_ids = {s.id for s in fa.suppliers.all()}
            removed_ids = current_ids - selected_ids
            if removed_ids:
                blocked = []
                for c in fa.contracts:
                    if c.supplier_id in removed_ids:
                        blocked.append(c.supplier.name if c.supplier else f"Fornecedor #{c.supplier_id}")
                if blocked:
                    raise ValueError("Não é possível retirar fornecedor(es) que já possuem contratos associados a este Acordo-Quadro: " + ", ".join(sorted(set(blocked))) + ".")

            fa.code = code
            fa.object = request.form["object"].strip()
            fa.procedure_type = request.form.get("procedure_type") or "Concurso Limitado por Convite"
            fa.start_date = parse_date(request.form.get("start_date"), None)
            fa.end_date = parse_date(request.form.get("end_date"), None)
            fa.estimated_value = num(request.form.get("estimated_value"))
            fa.status = request.form.get("status") or "Em vigor"
            fa.legal_basis = request.form.get("legal_basis")
            fa.document_ref = request.form.get("document_ref")
            fa.notes = request.form.get("notes")
            fa.suppliers = [s for s in suppliers_list if s.id in selected_ids]
            db.session.flush()
            for supplier in suppliers_list:
                if supplier.id in selected_ids:
                    allocation = num(request.form.get(f"supplier_limit_{supplier.id}"))
                    db.session.execute(text("UPDATE framework_supplier SET allocated_value=:v WHERE framework_id=:fid AND supplier_id=:sid"), {"v": allocation, "fid": fa.id, "sid": supplier.id})
            db.session.commit()
            flash(f"Acordo-Quadro {fa.code} actualizado com sucesso.")
            return redirect(url_for("framework_agreements"))
        except Exception as e:
            db.session.rollback()
            flash("Erro ao actualizar Acordo-Quadro: " + str(e))
    procedures = ["Concurso Limitado por Convite", "Concurso Público", "Contratação Simplificada", "Concurso Limitado por Prévia Qualificação", "Procedimento de Contratação Emergencial"]
    return render_template("framework_agreement_edit.html", fa=fa, suppliers=suppliers_list, procedures=procedures, allocations=allocations)

@app.route("/contracts", methods=["GET", "POST"])
@login_required
def contracts():
    suppliers_list=Supplier.query.order_by(Supplier.name).all()
    procedures=ProcurementProcedure.query.order_by(ProcurementProcedure.code).all()
    framework_agreements=FrameworkAgreement.query.order_by(FrameworkAgreement.code).all()
    if request.method == "POST":
        try:
            procedure = db.session.get(ProcurementProcedure, int(request.form["procedure_id"])) if request.form.get("procedure_id") else None
            supplier_id = int(request.form["supplier_id"]) if request.form.get("supplier_id") else None
            contract_type = request.form.get("contract_type") or "Serviços"
            procedure_type = request.form.get("procedure_type") or ""
            instrument_type = request.form.get("instrument_type") or "Contrato público"
            framework_agreement_id = int(request.form["framework_agreement_id"]) if request.form.get("framework_agreement_id") else None
            object_value = request.form.get("object", "").strip()

            # If a procedure is selected, its core data becomes the source of truth.
            if procedure:
                supplier_id = procedure.supplier_id or supplier_id
                contract_type = procedure.contract_category or contract_type
                procedure_type = procedure.procedure_type or procedure_type
                instrument_type = procedure.instrument_type or instrument_type
                framework_agreement_id = procedure.framework_agreement_id or framework_agreement_id
                object_value = procedure.object or object_value
            if not supplier_id:
                raise ValueError("Selecione o fornecedor ou associe um procedimento com fornecedor.")
            if not object_value:
                raise ValueError("Indique o objecto do contrato.")

            # A contract may be independent or may arise from an Acordo-Quadro.
            # When linked to an Acordo-Quadro, the supplier must be one of the
            # participating suppliers registered in that Acordo-Quadro.
            framework_agreement = None
            if framework_agreement_id:
                framework_agreement = db.session.get(FrameworkAgreement, framework_agreement_id)
                if not framework_agreement:
                    raise ValueError("O Acordo-Quadro seleccionado não existe.")
                participating_supplier_ids = {s.id for s in framework_agreement.suppliers.all()}
                if supplier_id not in participating_supplier_ids:
                    raise ValueError("O fornecedor seleccionado não participa no Acordo-Quadro indicado.")
                instrument_type = "Contrato ao abrigo de Acordo-Quadro"
            elif instrument_type == "Contrato ao abrigo de Acordo-Quadro":
                raise ValueError("Para um contrato ao abrigo de Acordo-Quadro, seleccione o Acordo-Quadro associado.")

            start_date=parse_date(request.form["start_date"])
            end_date=parse_date(request.form["end_date"])
            original=num(request.form["original_value"])
            current=num(request.form.get("current_value") or original)
            c=Contract(number=request.form["number"], supplier_id=supplier_id,
                procedure_id=procedure.id if procedure else None,
                object=object_value, contract_type=contract_type, procedure_type=procedure_type,
                start_date=start_date, end_date=end_date,
                original_value=original, current_value=current,
                renewal_allowed=bool(request.form.get("renewal_allowed")), renewal_count=int(request.form.get("renewal_count") or 0),
                cabimentado=bool(request.form.get("cabimentado")) or bool(procedure.cabimentado if procedure else False),
                cabimentacao_ref=request.form.get("cabimentacao_ref") or (procedure.cabimentacao_ref if procedure else None),
                tribunal_review_required=bool(request.form.get("tribunal_review_required")), tribunal_review_status=request.form.get("tribunal_review_status","Não aplicável"),
                guarantee_required=bool(request.form.get("guarantee_required")), guarantee_value=num(request.form.get("guarantee_value")),
                advance_percent=num(request.form.get("advance_percent")), amendments_percent=num(request.form.get("amendments_percent")),
                status=request.form.get("status","Em vigor"), document_ref=request.form.get("document_ref"), notes=request.form.get("notes"))
            db.session.add(c); db.session.commit(); run_compliance_checks()
            flash("Contrato registado e submetido ao motor de conformidade.")
        except Exception as e:
            db.session.rollback(); flash("Erro no contrato: "+str(e))
    contract_rows=[]
    for c in Contract.query.order_by(Contract.end_date).all():
        invoiced = money(db.session.query(func.coalesce(func.sum(SupplierInvoice.total),0)).filter(SupplierInvoice.contract_id==c.id).scalar())
        paid = money(db.session.query(func.coalesce(func.sum(SupplierPayment.amount),0)).filter(SupplierPayment.contract_id==c.id).scalar())
        balance = money(c.current_value) - invoiced
        execution = (invoiced / money(c.current_value) * 100) if money(c.current_value) else 0
        contract_rows.append({"obj":c,"invoiced":invoiced,"paid":paid,"balance":balance,"execution":execution})
    return render_template("contracts.html", rows=contract_rows, suppliers=suppliers_list, procedures=procedures, framework_agreements=framework_agreements)

@app.route("/procurement", methods=["GET", "POST"])
@login_required
def procurement():
    suppliers_list=Supplier.query.order_by(Supplier.name).all()
    framework_agreements=FrameworkAgreement.query.order_by(FrameworkAgreement.code).all()
    if request.method == "POST":
        try:
            p=ProcurementProcedure(code=request.form["code"], object=request.form["object"], contract_category=request.form["contract_category"],
                procedure_type=request.form["procedure_type"], instrument_type=request.form.get("instrument_type") or "Contrato público", framework_agreement_id=int(request.form["framework_agreement_id"]) if request.form.get("framework_agreement_id") else None, estimated_value=num(request.form["estimated_value"]), budget_year=int(request.form.get("budget_year") or date.today().year),
                budgeted=bool(request.form.get("budgeted")), cabimentado=bool(request.form.get("cabimentado")), cabimentacao_ref=request.form.get("cabimentacao_ref"),
                decision_date=parse_date(request.form.get("decision_date"), None), invitation_date=parse_date(request.form.get("invitation_date"), None),
                proposal_deadline=parse_date(request.form.get("proposal_deadline"), None), adjudication_date=parse_date(request.form.get("adjudication_date"), None),
                portal_registered=bool(request.form.get("portal_registered")), legal_basis=request.form.get("legal_basis"), justification=request.form.get("justification"),
                status=request.form.get("status","Em preparação"), supplier_id=int(request.form["supplier_id"]) if request.form.get("supplier_id") else None, created_by=session["uid"])
            db.session.add(p); db.session.commit(); run_compliance_checks(); flash("Procedimento registado e analisado.")
        except Exception as e: db.session.rollback(); flash("Erro no procedimento: "+str(e))
    return render_template("procurement.html", rows=ProcurementProcedure.query.order_by(ProcurementProcedure.id.desc()).all(), suppliers=suppliers_list, framework_agreements=framework_agreements)

@app.route("/alerts")
@login_required
def alerts():
    run_compliance_checks()
    return render_template("alerts.html", rows=ComplianceAlert.query.filter_by(resolved=False).order_by(ComplianceAlert.created_at.desc()).all())

@app.route("/alerts/resolve/<int:aid>")
@login_required
@admin_required
def resolve_alert(aid):
    a=db.session.get(ComplianceAlert, aid)
    if a: a.resolved=True; db.session.commit()
    return redirect(url_for("alerts"))

# -----------------------------------------------------------------------------
# Reports helpers / PDF generation
# -----------------------------------------------------------------------------
def _report_invoice_rows(supplier_id=None, status=None, framework_id=None, contract_id=None, start_date=None, end_date=None):
    # Reconcile previously imported OS records before building any report/export.
    # This fixes legacy imports where invoice_id was left empty.
    _reconcile_payment_orders(existing_only=True)
    q = SupplierInvoice.query
    if supplier_id: q = q.filter(SupplierInvoice.supplier_id == supplier_id)
    if framework_id:
        q = q.filter(or_(SupplierInvoice.framework_agreement_id == framework_id,
                         SupplierInvoice.contract.has(Contract.framework_agreement_id == framework_id)))
    if contract_id: q = q.filter(SupplierInvoice.contract_id == contract_id)
    if start_date: q = q.filter(SupplierInvoice.issue_date >= start_date)
    if end_date: q = q.filter(SupplierInvoice.issue_date <= end_date)
    rows = q.order_by(SupplierInvoice.issue_date, SupplierInvoice.number).all()
    if status and status != "Todos":
        if status == "Vencida":
            rows = [i for i in rows if money(i.total) > money(i.paid) and i.due_date and i.due_date < date.today()]
        else:
            rows = [i for i in rows if (i.status or "Pendente") == status]
    return rows


def _supplier_metrics(supplier_id, invoices=None):
    invoices = invoices if invoices is not None else _report_invoice_rows(supplier_id=supplier_id)
    invoiced = sum((money(i.total) for i in invoices), 0.0)
    paid = sum((money(i.paid) for i in invoices), 0.0)
    # Invoice.paid is used for report consistency, including filtered periods.
    # SupplierPayment remains the detailed reconciliation source in the payment module.
    return {"invoiced": invoiced, "paid": paid, "payable": max(invoiced-paid, 0.0), "count": len(invoices)}


def _pdf_money(v):
    return f"Kz {money(v):,.2f}".replace(",", " ")


def _supplier_pdf_bytes(supplier, invoices, generated_at=None):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("A biblioteca reportlab não está instalada.")
    generated_at = generated_at or datetime.now()
    metrics = _supplier_metrics(supplier.id, invoices)
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallBlue", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#1e3a5f")))
    styles.add(ParagraphStyle(name="TitleBlue", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#17365d")))
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm,
                            title=f"Relatório - {supplier.name}", author="ChivuGest")
    story = [Paragraph("CHIVUGEST", styles["TitleBlue"]),
             Paragraph("RELATÓRIO DE CONTA CORRENTE DO FORNECEDOR", styles["Heading2"]), Spacer(1, 5*mm)]
    info = [["Fornecedor", supplier.name], ["NIF", supplier.nif or "—"],
            ["Categoria", supplier.category or "—"], ["Data de emissão", generated_at.strftime("%d/%m/%Y %H:%M")]]
    t = Table(info, colWidths=[42*mm, 135*mm]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#eff6ff")),("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#dbe3ef")),("VALIGN",(0,0),(-1,-1),"TOP"),("FONTSIZE",(0,0),(-1,-1),9),("PADDING",(0,0),(-1,-1),6)])); story += [t, Spacer(1, 6*mm)]
    summary = [["Total faturado", "Total pago", "Saldo a pagar", "N.º faturas"],
               [_pdf_money(metrics["invoiced"]), _pdf_money(metrics["paid"]), _pdf_money(metrics["payable"]), str(metrics["count"])]]
    st = Table(summary, colWidths=[44*mm]*4); st.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f1f5f9")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#dbe3ef")),("ALIGN",(0,0),(-1,-1),"CENTER"),("FONTSIZE",(0,0),(-1,-1),9),("PADDING",(0,0),(-1,-1),6)])); story += [st, Spacer(1, 7*mm), Paragraph("FATURAS", styles["Heading3"])]
    data = [["Fatura","Ordem de Saque (N.º)","Data","Total","Pago","Saldo","Estado"]]
    for i in invoices:
        state = "Vencida" if money(i.total) > money(i.paid) and i.due_date and i.due_date < date.today() else (i.status or "Pendente")
        data.append([i.number, _invoice_payment_order_numbers(i) or "—", i.issue_date.strftime("%d/%m/%Y") if i.issue_date else "—", _pdf_money(i.total), _pdf_money(i.paid), _pdf_money(max(money(i.total)-money(i.paid),0)), state])
    if len(data)==1: data.append(["Sem faturas para os filtros selecionados","","","","","","",""])
    ft = Table(data, repeatRows=1, colWidths=[30*mm,35*mm,25*mm,27*mm,27*mm,27*mm,25*mm])
    ft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17365d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dbe3ef")),("FONTSIZE",(0,0),(-1,-1),7.5),("PADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story += [ft, Spacer(1, 7*mm), Paragraph(f"Relatório gerado automaticamente pelo ChivuGest em {generated_at.strftime('%d/%m/%Y %H:%M')}.", styles["SmallBlue"])]
    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica",7); canvas.setFillColor(colors.HexColor("#64748b")); canvas.drawString(16*mm, 8*mm, "ChivuGest — Gestão empresarial, fornecedores, contratos e conformidade"); canvas.drawRightString(194*mm, 8*mm, f"Página {doc.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0); return buf.getvalue()


def _safe_filename(value):
    value = unicodedata.normalize("NFKD", value or "fornecedor").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return value or "fornecedor"

# -----------------------------------------------------------------------------
# Reports
# -----------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    run_compliance_checks()
    supplier_id=request.args.get("supplier_id", type=int)
    framework_id=request.args.get("framework_id", type=int)
    contract_id=request.args.get("contract_id", type=int)
    status=request.args.get("status", "Todos")
    start_date=parse_date(request.args.get("start_date"), None)
    end_date=parse_date(request.args.get("end_date"), None)
    invoices=_report_invoice_rows(supplier_id, status, framework_id, contract_id, start_date, end_date)
    total=sum((money(i.total) for i in invoices), 0.0); paid=sum((money(i.paid) for i in invoices), 0.0); payable=max(total-paid,0.0)
    suppliers=Supplier.query.order_by(Supplier.name).all()
    frameworks=FrameworkAgreement.query.order_by(FrameworkAgreement.code).all()
    contracts=Contract.query.order_by(Contract.number).all()
    supplier_rows=[]
    for s in suppliers:
        sinv=[i for i in invoices if i.supplier_id==s.id]
        m=_supplier_metrics(s.id, sinv)
        os_count=PaymentOrder.query.filter_by(supplier_id=s.id).count()
        supplier_rows.append({"obj":s, **m, "invoice_count":len(sinv), "alert_count":ComplianceAlert.query.filter_by(supplier_id=s.id,resolved=False).count(), "document_count":SourceDocument.query.filter_by(supplier_id=s.id).count(), "os_count":os_count})
    return render_template("reports.html", total=total, paid=paid, payable=payable,
                           suppliers=len(suppliers), contracts=Contract.query.count(), framework_count=FrameworkAgreement.query.count(),
                           alerts=ComplianceAlert.query.filter_by(resolved=False).count(), invoices=len(invoices), procedures=ProcurementProcedure.query.count(),
                           rows=invoices, supplier_rows=supplier_rows, supplier_id=supplier_id, framework_id=framework_id, contract_id=contract_id,
                           status=status, start_date=request.args.get("start_date", ""), end_date=request.args.get("end_date", ""),
                           frameworks=frameworks, contracts_list=contracts, suppliers_list=suppliers)

def _invoice_payment_order_numbers(invoice):
    """Return all Ordem de Saque numbers associated with an invoice.

    The application has two historical representations of supplier payments:
    PaymentOrder (dedicated OS records) and SupplierPayment (older payment
    records where method="Ordem de Saque" and the OS number was stored in
    the receipt field). Reports must reconcile both representations.
    """
    numbers=[]

    # 1) Dedicated Ordem de Saque records.
    for order in getattr(invoice, "payment_orders", []) or []:
        value=(order.os_number or "").strip()
        if value and value not in numbers:
            numbers.append(value)

    # 2) Legacy/registered supplier payments whose payment method is OS.
    #    These are visible in the "Pagamentos registados" table and may
    #    already be linked to the invoice even when no PaymentOrder row exists.
    for payment in getattr(invoice, "payments", []) or []:
        method=_normalize_match_text(payment.method)
        if "ORDEMDE SAQUE" not in method:
            continue
        value=(payment.receipt or "").strip()
        if value and value not in numbers:
            numbers.append(value)

    return "; ".join(numbers)


def _report_export_rows(supplier_id=None, status="Todos", framework_id=None, contract_id=None, start_date=None, end_date=None):
    rows=_report_invoice_rows(supplier_id,status,framework_id,contract_id,start_date,end_date)
    data=[]
    for i in rows:
        total=money(i.total); paid=money(i.paid); saldo=max(total-paid,0.0)
        data.append([
            i.supplier.name if i.supplier else "",
            i.supplier.nif if i.supplier else "",
            i.framework_agreement.code if i.framework_agreement else (i.contract.framework_agreement.code if i.contract and i.contract.framework_agreement else ""),
            i.contract.number if i.contract else "",
            i.number or "",
            _invoice_payment_order_numbers(i),
            i.issue_date.isoformat() if i.issue_date else "",
            total, paid, saldo, i.status or ""
        ])
    return rows, data

@app.route("/reports/export")
@login_required
def report_export():
    supplier_id=request.args.get("supplier_id", type=int); status=request.args.get("status", "Todos")
    framework_id=request.args.get("framework_id", type=int); contract_id=request.args.get("contract_id", type=int)
    start_date=parse_date(request.args.get("start_date"), None); end_date=parse_date(request.args.get("end_date"), None)
    _, data=_report_export_rows(supplier_id,status,framework_id,contract_id,start_date,end_date)
    # Excel em Angola/Portugal normalmente interpreta ';' como separador CSV.
    # Mantemos UTF-8 com BOM, aspas e ponto decimal para evitar que todo o registo
    # seja colocado numa única célula quando aberto diretamente no Excel.
    out=io.StringIO(newline="")
    w=csv.writer(out, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(["Fornecedor","NIF","Acordo-Quadro","Contrato","Fatura","Ordem de Saque (N.º)","Data","Total","Pago","Saldo","Estado"])
    for r in data:
        w.writerow([*r[:7], f"{r[7]:.2f}", f"{r[8]:.2f}", f"{r[9]:.2f}", r[10]])
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=chivugest_relatorio_fornecedores.csv"})

@app.route("/reports/export.xlsx")
@login_required
def report_export_xlsx():
    supplier_id=request.args.get("supplier_id", type=int); status=request.args.get("status", "Todos")
    framework_id=request.args.get("framework_id", type=int); contract_id=request.args.get("contract_id", type=int)
    start_date=parse_date(request.args.get("start_date"), None); end_date=parse_date(request.args.get("end_date"), None)
    _, data=_report_export_rows(supplier_id,status,framework_id,contract_id,start_date,end_date)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    wb=Workbook(); ws=wb.active; ws.title="Relatório"
    headers=["Fornecedor","NIF","Acordo-Quadro","Contrato","Fatura","Ordem de Saque (N.º)","Data","Total","Pago","Saldo","Estado"]
    ws.append(headers)
    for r in data:
        ws.append(r)
    header_fill=PatternFill("solid", fgColor="17365D")
    header_font=Font(color="FFFFFF", bold=True)
    thin=Side(style="thin", color="D9E2F3")
    for cell in ws[1]:
        cell.fill=header_fill; cell.font=header_font; cell.alignment=Alignment(horizontal="center", vertical="center")
        cell.border=Border(bottom=thin)
    for row in ws.iter_rows(min_row=2, min_col=8, max_col=10):
        for cell in row:
            cell.number_format='#,##0.00'
    for col in range(1,12):
        max_len=max([len(str(ws.cell(row=r,column=col).value or "")) for r in range(1,ws.max_row+1)] or [10])
        ws.column_dimensions[get_column_letter(col)].width=min(max(max_len+3,12),50)
    # Keep financial values visible in Excel instead of showing #### when the
    # workbook is opened with a narrower default font/zoom.
    for col, width in {6:24, 8:18, 9:18, 10:18}.items():
        ws.column_dimensions[get_column_letter(col)].width=max(ws.column_dimensions[get_column_letter(col)].width, width)
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    ws.sheet_view.showGridLines=False
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",as_attachment=True,download_name="ChivuGest_Relatorio_Fornecedores.xlsx")

@app.route("/reports/supplier/<int:supplier_id>/pdf")
@login_required
def supplier_report_pdf(supplier_id):
    supplier=db.session.get(Supplier,supplier_id)
    if not supplier: abort(404)
    rows=_report_invoice_rows(supplier_id=supplier_id, status=request.args.get("status","Todos"), framework_id=request.args.get("framework_id",type=int), contract_id=request.args.get("contract_id",type=int), start_date=parse_date(request.args.get("start_date"),None), end_date=parse_date(request.args.get("end_date"),None))
    raw=_supplier_pdf_bytes(supplier,rows)
    return send_file(io.BytesIO(raw),mimetype="application/pdf",as_attachment=True,download_name=f"Relatorio_{_safe_filename(supplier.name)}.pdf")

@app.route("/reports/suppliers/pdf-zip")
@login_required
def suppliers_report_zip():
    import zipfile
    supplier_ids=request.args.getlist("supplier_id", type=int)
    suppliers=Supplier.query.filter(Supplier.id.in_(supplier_ids)).order_by(Supplier.name).all() if supplier_ids else Supplier.query.order_by(Supplier.name).all()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        for s in suppliers:
            rows=_report_invoice_rows(supplier_id=s.id, status=request.args.get("status","Todos"), framework_id=request.args.get("framework_id",type=int), contract_id=request.args.get("contract_id",type=int), start_date=parse_date(request.args.get("start_date"),None), end_date=parse_date(request.args.get("end_date"),None))
            z.writestr(f"Relatorio_{_safe_filename(s.name)}.pdf",_supplier_pdf_bytes(s,rows))
    buf.seek(0)
    return send_file(buf,mimetype="application/zip",as_attachment=True,download_name="ChivuGest_Relatorios_Fornecedores.zip")

@app.route("/reports/pdf")
@login_required
def reports_pdf():
    suppliers=Supplier.query.order_by(Supplier.name).all()
    rows=[]
    for s in suppliers:
        inv=_report_invoice_rows(supplier_id=s.id)
        m=_supplier_metrics(s.id,inv)
        rows.append((s,m))
    if not REPORTLAB_AVAILABLE: abort(500, description="reportlab não instalado")
    # Consolidated PDF is a single document with one supplier section per page.
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=15*mm,bottomMargin=15*mm,title="Relatório consolidado ChivuGest")
    styles=getSampleStyleSheet(); story=[Paragraph("CHIVUGEST — RELATÓRIO CONSOLIDADO DE FORNECEDORES",styles["Title"]),Spacer(1,6*mm)]
    for idx,(s,m) in enumerate(rows):
        if idx: story.append(PageBreak())
        story += [Paragraph(s.name,styles["Heading2"]), Paragraph(f"NIF: {s.nif or '—'}",styles["Normal"]),Spacer(1,4*mm),
                  Table([["Faturado","Pago","A pagar","Faturas"],[ _pdf_money(m["invoiced"]),_pdf_money(m["paid"]),_pdf_money(m["payable"]),str(m["count"])]],colWidths=[44*mm]*4)]
    doc.build(story); buf.seek(0)
    return send_file(buf,mimetype="application/pdf",as_attachment=True,download_name="ChivuGest_Relatorio_Consolidado.pdf")

@app.route("/reports/documents/upload", methods=["POST"])
@login_required
def report_document_upload():
    f=request.files.get("file"); supplier_id=request.form.get("supplier_id",type=int); document_type=request.form.get("document_type","Documento")
    if not f or not f.filename or not supplier_id: flash("Seleccione o fornecedor e o documento PDF."); return redirect(url_for("reports"))
    supplier=db.session.get(Supplier,supplier_id)
    if not supplier: flash("Fornecedor inválido."); return redirect(url_for("reports"))
    if not f.filename.lower().endswith(".pdf"): flash("A importação documental nesta área aceita apenas PDF."); return redirect(url_for("reports",supplier_id=supplier_id))
    raw=f.read(); digest=hashlib.sha256(raw).hexdigest()
    try:
        if SourceDocument.query.filter_by(source_hash=digest).first(): raise ValueError("Este PDF já foi importado.")
        parsed=extract_pdf_or_image(FileStorage(stream=io.BytesIO(raw), filename=f.filename, content_type=f.mimetype or "application/pdf"))
        doc=SourceDocument(document_type=document_type,document_number=parsed.get("number"),supplier_id=supplier_id,source_filename=f.filename,source_hash=digest,issue_date=parse_date(parsed.get("date"),None),amount=num(parsed.get("total")),extracted_data=json.dumps(parsed,ensure_ascii=False),import_confidence=int(parsed.get("confidence",0)),content=raw)
        inv_id=request.form.get("invoice_id",type=int)
        if inv_id:
            inv=db.session.get(SupplierInvoice,inv_id)
            if inv and inv.supplier_id==supplier_id: doc.invoice_id=inv.id
        db.session.add(doc); db.session.commit(); flash(f"PDF '{f.filename}' importado e associado a {supplier.name}.")
    except Exception as e:
        db.session.rollback(); flash("Erro ao importar PDF: "+str(e))
    return redirect(url_for("reports",supplier_id=supplier_id))

@app.route("/reports/documents/<int:doc_id>/download")
@login_required
def report_document_download(doc_id):
    doc=db.session.get(SourceDocument,doc_id)
    if not doc or not doc.content: abort(404)
    return send_file(io.BytesIO(doc.content),mimetype="application/pdf",as_attachment=True,download_name=doc.source_filename)

# -----------------------------------------------------------------------------
# Robust import centre
# -----------------------------------------------------------------------------
@app.route("/import", methods=["GET", "POST"])
@login_required
def import_center():
    if request.method == "POST":
        kind=request.form.get("kind")
        f=request.files.get("file")
        if not f or not f.filename: flash("Selecione um ficheiro."); return redirect(url_for("import_center"))
        try:
            if kind == "supplier_invoices_table":
                rows=uploaded_rows(f); n=0
                for r in rows:
                    supplier_name=str(row_value(r,"fornecedor","supplier","emitente")).strip()
                    number=str(row_value(r,"numero","fatura","factura","invoice_number")).strip()
                    total=num(row_value(r,"total","valor","amount"))
                    if not supplier_name or not number or total <= 0: continue
                    s=Supplier.query.filter_by(name=supplier_name).first()
                    if not s:
                        s=Supplier(name=supplier_name,nif=str(row_value(r,"nif","nuit")),contracting_type="Outro / Regime especial")
                        db.session.add(s); db.session.flush()
                    inv=SupplierInvoice(number=number,supplier_id=s.id,issue_date=parse_date(row_value(r,"data","issue_date")),
                        due_date=parse_date(row_value(r,"vencimento","due_date"),None),subtotal=num(row_value(r,"subtotal")),vat=num(row_value(r,"iva","vat")),
                        total=total,paid=num(row_value(r,"pago","paid")),currency=str(row_value(r,"currency","moeda")) or "AOA",
                        source_filename=f.filename)
                    inv.status="Paga" if inv.paid>=inv.total else ("Parcial" if inv.paid>0 else "Pendente")
                    db.session.add(inv); n+=1
                db.session.commit(); flash(f"Importação concluída: {n} fatura(s).")
            elif kind == "pdf_invoice":
                parsed=extract_invoice_document(f)
                existing=SupplierInvoice.query.filter_by(source_hash=parsed["hash"]).first()
                if existing: raise ValueError("Este documento já foi importado anteriormente.")
                session["invoice_import"] = parsed
                return render_template("invoice_review.html", data=parsed)
            else:
                raise ValueError("Tipo de importação desconhecido.")
        except Exception as e:
            db.session.rollback(); flash("Erro na importação: "+str(e))
    return render_template("import_center.html")

@app.route("/import/invoice-confirm", methods=["POST"])
@login_required
def invoice_confirm():
    data=session.pop("invoice_import", {})
    try:
        supplier_name=request.form["supplier"]
        s=Supplier.query.filter_by(name=supplier_name).first()
        if not s:
            s=Supplier(name=supplier_name,nif=request.form.get("nif"),contracting_type=request.form.get("contracting_type") or "Outro / Regime especial")
            db.session.add(s); db.session.flush()
        inv=SupplierInvoice(number=request.form["number"], supplier_id=s.id, issue_date=parse_date(request.form.get("date")),
            due_date=parse_date(request.form.get("due_date"),None), subtotal=num(request.form.get("subtotal")), vat=num(request.form.get("vat")),
            total=num(request.form.get("total")), paid=0, currency=request.form.get("currency") or "AOA", source_filename=data.get("filename"),
            source_hash=data.get("hash"), raw_text="", extracted_data=json.dumps(data,ensure_ascii=False), import_confidence=int(data.get("confidence",0)))
        inv.status="Pendente"; db.session.add(inv); db.session.commit(); flash("Fatura importada após revisão.")
    except Exception as e: db.session.rollback(); flash("Erro ao confirmar a fatura: "+str(e))
    return redirect(url_for("supplier_invoices"))

# -----------------------------------------------------------------------------
# Settings / legal library / users
# -----------------------------------------------------------------------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    if request.method == "POST":
        for rule in LegalRule.query.all():
            if rule.parameter and rule.parameter in request.form:
                try: rule.value=Decimal(request.form[rule.parameter])
                except InvalidOperation: pass
        db.session.commit(); flash("Parâmetros legais atualizados.")
    return render_template("settings.html", rules=LegalRule.query.order_by(LegalRule.id).all(), documents=LegalDocument.query.order_by(LegalDocument.id).all(), versions=LegalVersion.query.order_by(LegalVersion.effective_from.desc()).all(), checks=LegalUpdateCheck.query.order_by(LegalUpdateCheck.checked_at.desc()).all())

@app.route("/legal/check", methods=["POST"])
@login_required
@admin_required
def legal_check():
    results = check_legal_updates()
    changed = sum(1 for _, status in results if "Alteração" in status)
    errors = sum(1 for _, status in results if "Erro" in status)
    if changed:
        flash(f"Verificação concluída: {changed} fonte(s) com alteração detectada. A validação humana é necessária antes de alterar regras.")
    elif errors:
        flash(f"Verificação concluída com {errors} erro(s) de acesso às fontes.")
    else:
        flash("Verificação concluída: não foram detectadas alterações nas fontes configuradas.")
    return redirect(url_for("legal_library"))

@app.route("/legal")
@login_required
def legal_library():
    documents=LegalDocument.query.order_by(LegalDocument.id).all()
    rules=LegalRule.query.filter_by(active=True).order_by(LegalRule.id).all()
    checks=LegalUpdateCheck.query.order_by(LegalUpdateCheck.checked_at.desc()).all()
    return render_template("legal.html", documents=documents, rules=rules, checks=checks)

# -----------------------------------------------------------------------------
# Administrator-only data maintenance (edit/delete across the application)
# -----------------------------------------------------------------------------
ADMIN_MODELS = {
    "supplier": Supplier, "supplier_invoice": SupplierInvoice, "supplier_payment": SupplierPayment,
    "contract": Contract, "procedure": ProcurementProcedure, "client": Client, "invoice": Invoice,
    "payment": Payment, "user": User, "legal_rule": LegalRule, "legal_document": LegalDocument, "legal_version": LegalVersion, "legal_update_check": LegalUpdateCheck,
    "alert": ComplianceAlert, "payment_order": PaymentOrder, "source_document": SourceDocument,
}
# Fields that are generated/system-only or intentionally removed from the supplier UI.
ADMIN_EXCLUDED = {"id", "created_at", "password_hash", "source_hash", "raw_text", "extracted_data", "import_confidence"}
ADMIN_MODEL_EXCLUDED = {"Supplier": {"portal_status", "certification_status", "tax_clearance_expiry", "social_security_expiry", "professional_license_expiry", "blocked"}}


def admin_field_specs(model):
    specs=[]
    mapper=inspect(model)
    for col in mapper.columns:
        if col.name in ADMIN_EXCLUDED or col.name in ADMIN_MODEL_EXCLUDED.get(model.__name__, set()):
            continue
        if col.name == "created_by":
            continue
        kind="text"
        if col.type.__class__.__name__ in ("Boolean",): kind="bool"
        elif col.type.__class__.__name__ in ("Date",): kind="date"
        elif col.type.__class__.__name__ in ("Integer",): kind="int"
        elif col.type.__class__.__name__ in ("Numeric", "Float", "REAL"):
            kind="number"
        # Foreign keys get a select with human-readable choices.
        fk=next(iter(col.foreign_keys), None)
        options=[]
        if fk:
            target=fk.column.table.name
            target_model=next((m for m in ADMIN_MODELS.values() if m.__tablename__==target), None)
            if target_model:
                for obj in target_model.query.order_by(target_model.id).all():
                    label=getattr(obj,"name",None) or getattr(obj,"number",None) or getattr(obj,"code",None) or str(obj.id)
                    options.append((obj.id,label))
                kind="select"
        specs.append({"name":col.name,"label":col.name.replace("_"," ").title(),"kind":kind,"options":options,"value":None})
    return specs

@app.route("/admin/data")
@login_required
@admin_required
def admin_data():
    labels={"supplier":"Fornecedores","supplier_invoice":"Faturas de fornecedores","supplier_payment":"Pagamentos de fornecedores","contract":"Contratos","procedure":"Contratação pública","client":"Clientes","invoice":"Faturas legadas","payment":"Pagamentos legados","user":"Utilizadores","legal_rule":"Regras legais","legal_document":"Documentos legais","alert":"Alertas", "payment_order":"Ordens de Saque", "source_document":"Documentos Fonte", "legal_version":"Versões legais", "legal_update_check":"Verificações legais"}
    datasets=[(k, ADMIN_MODELS[k], ADMIN_MODELS[k].query.order_by(ADMIN_MODELS[k].id.desc()).limit(100).all()) for k in ADMIN_MODELS]
    return render_template("admin_data.html", datasets=datasets, labels=labels)

@app.route("/admin/edit/<model>/<int:record_id>", methods=["GET","POST"])
@login_required
@admin_required
def admin_edit(model, record_id):
    cls=ADMIN_MODELS.get(model)
    if not cls: return redirect(url_for("admin_data"))
    obj=db.session.get(cls, record_id)
    if not obj:
        flash("Registo não encontrado.")
        return redirect(url_for("admin_data"))
    specs=admin_field_specs(cls)
    for spec in specs:
        spec["value"] = getattr(obj, spec["name"], None)
    if request.method=="POST":
        try:
            for spec in specs:
                name=spec["name"]; raw=request.form.get(name)
                if spec["kind"]=="bool": val=(raw=="on")
                elif spec["kind"]=="date": val=parse_date(raw, None)
                elif spec["kind"]=="int": val=int(raw) if raw not in (None,"") else None
                elif spec["kind"]=="number": val=num(raw) if raw not in (None,"") else None
                elif spec["kind"]=="select": val=int(raw) if raw not in (None,"") else None
                else: val=raw
                setattr(obj,name,val)
            db.session.commit()
            audit("EDIT", cls.__name__, obj.id, "Registo alterado pelo administrador")
            if cls in (Supplier, Contract, ProcurementProcedure, SupplierInvoice, SupplierPayment): run_compliance_checks()
            flash("Registo alterado com sucesso.")
            return redirect(url_for("admin_data"))
        except Exception as e:
            db.session.rollback(); flash("Não foi possível alterar o registo: "+str(e))
    return render_template("admin_edit.html", obj=obj, specs=specs, model=model)

@app.route("/admin/delete/<model>/<int:record_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete(model, record_id):
    cls=ADMIN_MODELS.get(model)
    if not cls: return redirect(url_for("admin_data"))
    obj=db.session.get(cls, record_id)
    if not obj:
        flash("Registo não encontrado."); return redirect(url_for("admin_data"))
    if cls is User and obj.id == session.get("uid"):
        flash("O administrador não pode eliminar a própria conta."); return redirect(url_for("admin_data"))
    try:
        db.session.delete(obj); db.session.commit(); audit("DELETE", cls.__name__, record_id, "Registo eliminado pelo administrador"); flash("Registo eliminado com sucesso.")
    except IntegrityError:
        db.session.rollback(); flash("Não foi possível eliminar: existem registos relacionados. Altere ou elimine primeiro os registos dependentes.")
    except Exception as e:
        db.session.rollback(); flash("Erro ao eliminar: "+str(e))
    return redirect(url_for("admin_data"))

@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method=="POST":
        try:
            db.session.add(User(name=request.form["name"], username=request.form["username"], password_hash=generate_password_hash(request.form["password"]), role=request.form["role"], active=True))
            db.session.commit(); flash("Utilizador criado.")
        except IntegrityError: db.session.rollback(); flash("Nome de utilizador já existe.")
    return render_template("users.html", rows=User.query.order_by(User.name).all())

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = db.session.get(User, session["uid"])
    if not user:
        session.clear()
        return redirect(url_for("login"))
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(user.password_hash, current):
            flash("A palavra-passe atual está incorreta.")
        elif len(new_password) < 8:
            flash("A nova palavra-passe deve ter pelo menos 8 caracteres.")
        elif not re.search(r"[A-Z]", new_password) or not re.search(r"[a-z]", new_password) or not re.search(r"\d", new_password):
            flash("A nova palavra-passe deve conter pelo menos uma letra maiúscula, uma minúscula e um número.")
        elif new_password != confirm:
            flash("A confirmação da nova palavra-passe não coincide.")
        elif new_password == current:
            flash("A nova palavra-passe deve ser diferente da atual.")
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Palavra-passe alterada com sucesso.")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")

@app.route("/users/reset-password/<int:uid>", methods=["GET", "POST"])
@login_required
@admin_required
def reset_password(uid):
    user = db.session.get(User, uid)
    if not user:
        flash("Utilizador não encontrado.")
        return redirect(url_for("users"))
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if len(new_password) < 8:
            flash("A nova palavra-passe deve ter pelo menos 8 caracteres.")
        elif not re.search(r"[A-Z]", new_password) or not re.search(r"[a-z]", new_password) or not re.search(r"\d", new_password):
            flash("A nova palavra-passe deve conter pelo menos uma letra maiúscula, uma minúscula e um número.")
        elif new_password != confirm:
            flash("A confirmação da nova palavra-passe não coincide.")
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash(f"Palavra-passe de {user.username} redefinida com sucesso.")
            return redirect(url_for("users"))
    return render_template("reset_password.html", user=user)

@app.route("/users/toggle/<int:uid>")
@login_required
@admin_required
def toggle_user(uid):
    u=db.session.get(User,uid)
    if u and u.id != session["uid"]: u.active=not u.active; db.session.commit()
    return redirect(url_for("users"))

# -----------------------------------------------------------------------------
# Legacy customer module kept available for backwards compatibility.
# -----------------------------------------------------------------------------
@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    if request.method=="POST":
        db.session.add(Client(name=request.form["name"],nif=request.form.get("nif"),phone=request.form.get("phone"),email=request.form.get("email"))); db.session.commit(); flash("Cliente criado.")
    return render_template("clients.html", rows=Client.query.order_by(Client.name).all())

@app.route("/legacy-invoices", methods=["GET", "POST"])
@login_required
def legacy_invoices():
    clients=Client.query.order_by(Client.name).all()
    if request.method=="POST":
        db.session.add(Invoice(number=request.form["number"],client_id=int(request.form["client_id"]),date=parse_date(request.form["date"]),due_date=parse_date(request.form["due_date"]),amount=num(request.form["amount"]),paid=0,status="Pendente")); db.session.commit(); flash("Fatura de cliente registada.")
    return render_template("invoices.html", rows=Invoice.query.order_by(Invoice.id.desc()).all(), clients=clients)

@app.route("/export")
@login_required
def export():
    out=io.StringIO(newline=""); w=csv.writer(out, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(["Fornecedor","NIF","Fatura","Ordem de Saque (N.º)","Data","Total","Pago","Saldo","Estado"])
    for i in SupplierInvoice.query.order_by(SupplierInvoice.issue_date).all():
        w.writerow([i.supplier.name,i.supplier.nif or "",i.number,_invoice_payment_order_numbers(i),i.issue_date.isoformat(),f"{money(i.total):.2f}",f"{money(i.paid):.2f}",f"{money(i.total)-money(i.paid):.2f}",i.status])
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=chivugest_faturas_fornecedores.csv"})

@app.route("/health")
def health(): return "OK", 200

# -----------------------------------------------------------------------------
# Database initialisation. Existing tables are preserved. New tables are added.
# -----------------------------------------------------------------------------
def ensure_schema():
    """Lightweight additive migration for existing SQLite/PostgreSQL installations."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "framework_agreement" not in tables:
        FrameworkAgreement.__table__.create(bind=db.engine, checkfirst=True)
    if "framework_supplier" not in tables:
        framework_supplier.create(bind=db.engine, checkfirst=True)
    def add_column(table, column, ddl):
        if table not in inspect(db.engine).get_table_names(): return
        names={c["name"] for c in inspect(db.engine).get_columns(table)}
        if column not in names:
            with db.engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    add_column("procurement_procedure", "instrument_type", "VARCHAR(100)")
    add_column("procurement_procedure", "framework_agreement_id", "INTEGER")
    add_column("contract", "instrument_type", "VARCHAR(100)")
    add_column("contract", "framework_agreement_id", "INTEGER")
    add_column("supplier_invoice", "framework_agreement_id", "INTEGER")
    add_column("supplier_payment", "framework_agreement_id", "INTEGER")
    add_column("payment_order", "framework_agreement_id", "INTEGER")
    add_column("framework_supplier", "allocated_value", "NUMERIC(18,2) NOT NULL DEFAULT 0")
    add_column("compliance_alert", "framework_agreement_id", "INTEGER")
    add_column("supplier", "contracting_type", "VARCHAR(80)")
    # Document repository fields: keep PDFs associated with suppliers and optional financial/contract records.
    add_column("source_document", "invoice_id", "INTEGER")
    add_column("source_document", "contract_id", "INTEGER")
    add_column("source_document", "framework_agreement_id", "INTEGER")
    add_column("source_document", "content", "BYTEA" if db.engine.dialect.name == "postgresql" else "BLOB")
    # Existing suppliers remain valid; this field is now legacy and no longer used by the UI.
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE supplier SET contracting_type='Não aplicável' WHERE contracting_type IS NULL OR contracting_type=''"))
        conn.execute(text("UPDATE procurement_procedure SET instrument_type='Contrato público' WHERE instrument_type IS NULL OR instrument_type=''"))
        conn.execute(text("UPDATE contract SET instrument_type='Contrato público' WHERE instrument_type IS NULL OR instrument_type=''"))
        # Backfill the new traceability link for legacy records that already had a contract.
        if "supplier_invoice" in inspect(db.engine).get_table_names():
            conn.execute(text("UPDATE supplier_invoice SET framework_agreement_id=(SELECT framework_agreement_id FROM contract WHERE contract.id=supplier_invoice.contract_id) WHERE framework_agreement_id IS NULL AND contract_id IS NOT NULL"))
        if "supplier_payment" in inspect(db.engine).get_table_names():
            conn.execute(text("UPDATE supplier_payment SET framework_agreement_id=(SELECT framework_agreement_id FROM contract WHERE contract.id=supplier_payment.contract_id) WHERE framework_agreement_id IS NULL AND contract_id IS NOT NULL"))
        if "payment_order" in inspect(db.engine).get_table_names():
            conn.execute(text("UPDATE payment_order SET framework_agreement_id=(SELECT framework_agreement_id FROM contract WHERE contract.id=payment_order.contract_id) WHERE framework_agreement_id IS NULL AND contract_id IS NOT NULL"))

def init_db():
    with app.app_context():
        db.create_all()
        ensure_schema()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(name="Administrador",username="admin",password_hash=generate_password_hash("admin123"),role="admin"))
            db.session.commit()
        seed_legal_data()
        seed_legal_versions()
        # Make sure legacy installations that had no new tables are initialized.
        run_compliance_checks()

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
