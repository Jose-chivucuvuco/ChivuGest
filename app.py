import os, csv, io, re, secrets
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
database_url = os.environ.get("DATABASE_URL", "sqlite:///chivugest.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
db = SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(150),nullable=False)
    username=db.Column(db.String(80),unique=True,nullable=False,index=True)
    password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(30),nullable=False,default="user")
    active=db.Column(db.Boolean,nullable=False,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class Client(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(200),nullable=False,index=True)
    nif=db.Column(db.String(30))
    phone=db.Column(db.String(50))
    email=db.Column(db.String(150))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class Invoice(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    number=db.Column(db.String(80),nullable=False,index=True)
    client_id=db.Column(db.Integer,db.ForeignKey("client.id"),nullable=False)
    date=db.Column(db.Date,nullable=False)
    due_date=db.Column(db.Date,nullable=False)
    amount=db.Column(db.Numeric(18,2),nullable=False)
    paid=db.Column(db.Numeric(18,2),nullable=False,default=0)
    status=db.Column(db.String(20),nullable=False,default="Pendente")
    client=db.relationship("Client",backref="invoices")

class Payment(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    receipt=db.Column(db.String(80),nullable=False,index=True)
    client_id=db.Column(db.Integer,db.ForeignKey("client.id"),nullable=False)
    invoice_id=db.Column(db.Integer,db.ForeignKey("invoice.id"))
    date=db.Column(db.Date,nullable=False)
    method=db.Column(db.String(50),nullable=False)
    amount=db.Column(db.Numeric(18,2),nullable=False)
    client=db.relationship("Client",backref="payments")
    invoice=db.relationship("Invoice",backref="payments")

def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get("uid"):
            return redirect(url_for("login"))
        u=db.session.get(User,session["uid"])
        if not u or not u.active:
            session.clear(); return redirect(url_for("login"))
        return f(*a,**k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if session.get("role")!="admin":
            flash("Acesso reservado ao administrador.")
            return redirect(url_for("dashboard"))
        return f(*a,**k)
    return w

@app.context_processor
def globals():
    return {"today":date.today()}

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(name="Administrador",username="admin",
                                password_hash=generate_password_hash("admin123"),role="admin"))
            db.session.commit()

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(username=request.form["username"]).first()
        if u and u.active and check_password_hash(u.password_hash,request.form["password"]):
            session.update(uid=u.id,name=u.name,role=u.role)
            return redirect(url_for("dashboard"))
        flash("Utilizador ou palavra-passe inválidos.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    billed=db.session.query(func.coalesce(func.sum(Invoice.amount),0)).scalar() or 0
    received=db.session.query(func.coalesce(func.sum(Payment.amount),0)).scalar() or 0
    receivable=float(billed)-float(received)
    late=db.session.query(func.coalesce(func.sum(Invoice.amount-Invoice.paid),0)).filter(Invoice.due_date<date.today(),Invoice.amount>Invoice.paid).scalar() or 0
    months=db.session.query(func.strftime("%Y-%m",Payment.date).label("m"),func.sum(Payment.amount).label("v")).group_by("m").order_by("m").all()
    recent=Payment.query.order_by(Payment.id.desc()).limit(10).all()
    return render_template("dashboard.html",billed=billed,received=received,receivable=receivable,late=late,months=months,recent=recent,clients=Client.query.count())

@app.route("/clients",methods=["GET","POST"])
@login_required
def clients():
    if request.method=="POST":
        db.session.add(Client(name=request.form["name"],nif=request.form.get("nif"),phone=request.form.get("phone"),email=request.form.get("email")))
        db.session.commit(); flash("Cliente criado.")
        return redirect(url_for("clients"))
    return render_template("clients.html",rows=Client.query.order_by(Client.name).all())

def parse_date(s):
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
        try:return datetime.strptime(str(s),fmt).date()
        except:pass
    return date.today()

@app.route("/invoices",methods=["GET","POST"])
@login_required
def invoices():
    clients=Client.query.order_by(Client.name).all()
    if request.method=="POST":
        db.session.add(Invoice(number=request.form["number"],client_id=int(request.form["client_id"]),
            date=parse_date(request.form["date"]),due_date=parse_date(request.form["due_date"]),
            amount=float(request.form["amount"]),paid=0,status="Pendente"))
        db.session.commit(); flash("Fatura registada.")
        return redirect(url_for("invoices"))
    return render_template("invoices.html",rows=Invoice.query.order_by(Invoice.id.desc()).all(),clients=clients)

@app.route("/payments",methods=["GET","POST"])
@login_required
def payments():
    clients=Client.query.order_by(Client.name).all()
    invoices=Invoice.query.order_by(Invoice.id.desc()).all()
    if request.method=="POST":
        amount=float(request.form["amount"])
        inv=db.session.get(Invoice,int(request.form["invoice_id"])) if request.form.get("invoice_id") else None
        if inv:
            inv.paid=float(inv.paid)+amount
            inv.status="Paga" if inv.paid>=float(inv.amount) else "Parcial"
        db.session.add(Payment(receipt=request.form["receipt"],client_id=int(request.form["client_id"]),
                               invoice_id=inv.id if inv else None,date=parse_date(request.form["date"]),
                               method=request.form["method"],amount=amount))
        db.session.commit(); flash("Pagamento registado.")
        return redirect(url_for("payments"))
    return render_template("payments.html",rows=Payment.query.order_by(Payment.id.desc()).all(),clients=clients,invoices=invoices)

@app.route("/current")
@login_required
def current():
    entries=[]
    for i in Invoice.query.order_by(Invoice.date,Invoice.id).all():
        entries.append((i.date,i.number,"Fatura",float(i.amount),0))
    for p in Payment.query.order_by(Payment.date,Payment.id).all():
        entries.append((p.date,p.receipt,"Pagamento",0,float(p.amount)))
    entries.sort(key=lambda x:(x[0],x[1]))
    bal=0; rows=[]
    for e in entries:
        bal += e[3]-e[4]; rows.append((e,bal))
    return render_template("current.html",rows=rows)

def money(v):
    return float(v or 0)

@app.route("/export")
@login_required
def export():
    kind=request.args.get("kind","invoices"); out=io.StringIO(); w=csv.writer(out)
    if kind=="payments":
        w.writerow(["Recibo","Cliente","Fatura","Data","Meio","Valor"])
        for p in Payment.query.order_by(Payment.date).all():
            w.writerow([p.receipt,p.client.name,p.invoice.number if p.invoice else "",p.date.isoformat(),p.method,money(p.amount)])
        fn="chivugest_pagamentos.csv"
    else:
        w.writerow(["Numero","Cliente","NIF","Data","Vencimento","Valor","Pago","Saldo","Estado"])
        for i in Invoice.query.order_by(Invoice.date).all():
            w.writerow([i.number,i.client.name,i.client.nif or "",i.date.isoformat(),i.due_date.isoformat(),money(i.amount),money(i.paid),money(i.amount)-money(i.paid),i.status])
        fn="chivugest_faturas.csv"
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename={fn}"})

def uploaded_rows(f):
    name=(f.filename or "").lower()
    if name.endswith(".xlsx"):
        if not load_workbook: raise ValueError("openpyxl não instalado.")
        wb=load_workbook(f,read_only=True,data_only=True); ws=wb.active
        data=list(ws.iter_rows(values_only=True)); wb.close()
        if not data:return []
        headers=[str(x).strip().lower() if x is not None else "" for x in data[0]]
        return [dict(zip(headers,r)) for r in data[1:] if any(x is not None for x in r)]
    if name.endswith(".csv"):
        raw=f.read()
        try:s=raw.decode("utf-8-sig")
        except:s=raw.decode("cp1252")
        return list(csv.DictReader(io.StringIO(s)))
    raise ValueError("Use CSV ou XLSX para esta importação.")

def rv(r,*keys):
    for k in keys:
        for kk in (k,k.lower(),k.lower().replace(" ","_")):
            if kk in r and r[kk] not in ("",None):return r[kk]
    return ""

def num(v):
    s=str(v).replace("Kz","").replace("kz","").replace(" ","")
    if "," in s and "." in s:
        s=s.replace(".","").replace(",",".") if s.rfind(",")>s.rfind(".") else s.replace(",","")
    elif "," in s:s=s.replace(",",".")
    return float(s)

@app.route("/import",methods=["GET","POST"])
@login_required
def import_data():
    if request.method=="POST":
        kind=request.form["kind"]; f=request.files.get("file")
        try:
            rows=uploaded_rows(f); n=0
            for r in rows:
                client_name=str(rv(r,"cliente","client","nome_cliente")).strip()
                if not client_name: continue
                c=Client.query.filter_by(name=client_name).first()
                if not c:
                    c=Client(name=client_name,nif=str(rv(r,"nif","nuit"))); db.session.add(c); db.session.flush()
                if kind=="invoices":
                    amount=num(rv(r,"valor","amount","total")); number=str(rv(r,"numero","number","fatura","factura"))
                    if not number or not amount: continue
                    paid=num(rv(r,"pago","pago_total","paid") or 0)
                    db.session.add(Invoice(number=number,client_id=c.id,date=parse_date(rv(r,"data","date")),
                      due_date=parse_date(rv(r,"vencimento","due_date","data_vencimento")),amount=amount,paid=paid,
                      status="Paga" if paid>=amount else ("Parcial" if paid>0 else "Pendente")))
                else:
                    amount=num(rv(r,"valor","amount","valor_pago")); receipt=str(rv(r,"recibo","receipt"))
                    if not receipt or not amount: continue
                    inv_no=str(rv(r,"fatura","invoice","numero_fatura")); inv=Invoice.query.filter_by(number=inv_no).first() if inv_no else None
                    if inv:
                        inv.paid=float(inv.paid)+amount; inv.status="Paga" if inv.paid>=float(inv.amount) else "Parcial"
                    db.session.add(Payment(receipt=receipt,client_id=c.id,invoice_id=inv.id if inv else None,
                      date=parse_date(rv(r,"data","date")),method=str(rv(r,"meio","method","metodo") or "Transferência"),amount=amount))
                n+=1
            db.session.commit(); flash(f"Importação concluída: {n} registos.")
        except Exception as e:
            db.session.rollback(); flash("Erro na importação: "+str(e))
        return redirect(url_for("import_data"))
    return render_template("import.html")

@app.route("/pdf-preview",methods=["POST"])
@login_required
def pdf_preview():
    f=request.files.get("file")
    if not f or not f.filename.lower().endswith(".pdf"): flash("Selecione um PDF."); return redirect(url_for("import_data"))
    try:
        if fitz is None: raise ValueError("PyMuPDF não instalado.")
        raw=f.read(); doc=fitz.open(stream=raw,filetype="pdf"); texts=[]
        for page in doc:
            txt=page.get_text("text").strip()
            if len(re.sub(r"\s+","",txt))<30:
                if pytesseract is None: raise ValueError("OCR não instalado.")
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
                img=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
                txt=pytesseract.image_to_string(img,lang="por+eng")
            texts.append(txt)
        text="\n".join(texts)
        def find(pats):
            for p in pats:
                m=re.search(p,text,re.I|re.M)
                if m:return m.group(1).strip()
            return ""
        number=find([r"(?:fatura|factura|invoice)\s*(?:n[ºo.]?|numero|número)?\s*[:#-]?\s*([A-Z0-9./_-]{3,})",r"\b(FT|FR)[\s:-]*([0-9]{2,})\b"])
        client=find([r"(?:cliente|adquirente|comprador|customer)\s*[:#-]\s*(.+)",r"(?:nome)\s*[:#-]\s*(.+)"])
        nif=find([r"(?:NIF|NUIT)\s*[:#-]?\s*([0-9]{8,15})"])
        dates=re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b",text)
        total=find([r"(?:total a pagar|total|valor total|total factura|total fatura)\s*[:\-]?\s*(?:Kz|AOA|AKZ)?\s*([0-9][0-9\s.,]*)"])
        fields={"number":number,"client":client,"nif":nif,"date":dates[0] if dates else "","due_date":dates[1] if len(dates)>1 else "","amount":num(total) if total else 0}
        return render_template("pdf_preview.html",fields=fields,text=text[:15000])
    except Exception as e:
        flash("Erro no PDF/OCR: "+str(e)); return redirect(url_for("import_data"))

@app.route("/pdf-confirm",methods=["POST"])
@login_required
def pdf_confirm():
    try:
        client=Client.query.filter_by(name=request.form["client"]).first()
        if not client:
            client=Client(name=request.form["client"],nif=request.form.get("nif")); db.session.add(client); db.session.flush()
        amount=float(request.form["amount"])
        db.session.add(Invoice(number=request.form["number"],client_id=client.id,date=parse_date(request.form["date"]),
            due_date=parse_date(request.form["due_date"]),amount=amount,paid=0,status="Pendente"))
        db.session.commit(); flash("Fatura PDF importada.")
    except Exception as e: db.session.rollback(); flash("Erro ao gravar: "+str(e))
    return redirect(url_for("invoices"))

@app.route("/users",methods=["GET","POST"])
@login_required
@admin_required
def users():
    if request.method=="POST":
        try:
            db.session.add(User(name=request.form["name"],username=request.form["username"],
                password_hash=generate_password_hash(request.form["password"]),role=request.form["role"],active=True))
            db.session.commit(); flash("Utilizador criado.")
        except IntegrityError:
            db.session.rollback(); flash("Nome de utilizador já existe.")
    return render_template("users.html",rows=User.query.order_by(User.name).all())

@app.route("/users/toggle/<int:uid>")
@login_required
@admin_required
def toggle_user(uid):
    u=db.session.get(User,uid)
    if u and u.id!=session["uid"]:
        u.active=not u.active; db.session.commit()
    return redirect(url_for("users"))

@app.route("/health")
def health(): return "OK",200

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
