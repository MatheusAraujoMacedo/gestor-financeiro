from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from sqlalchemy import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import calendar as cal_module
import json
import csv
import io
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__)

# Configurações para deploy / local
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gestor-financeiro-secret-key-2026')

# Configuração do Cloudinary (usar variáveis de ambiente para a Cloud Name e chaves)
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
  api_key = os.environ.get('CLOUDINARY_API_KEY', '439547935185919'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET', '3lPycV2JNER-wcV96W1l1sC4vmg')
)

db_url = os.environ.get('DATABASE_URL', 'sqlite:///gestor.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'
login_manager.login_message_category = 'info'


# =============================================
# MODELOS
# =============================================

# Tabela associativa Tag <-> Transacao
transacao_tags = db.Table('transacao_tags',
    db.Column('transacao_id', db.Integer, db.ForeignKey('transacao.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    tema = db.Column(db.String(10), default='dark')  # 'dark' ou 'light'
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Login por e-mail
    codigo_verificacao = db.Column(db.String(6), nullable=True)
    codigo_expiracao = db.Column(db.DateTime, nullable=True)

    # Relacionamentos
    transacoes = db.relationship('Transacao', backref='dono', lazy=True, cascade='all, delete-orphan')
    contas = db.relationship('Conta', backref='dono', lazy=True, cascade='all, delete-orphan')
    categorias = db.relationship('Categoria', backref='dono', lazy=True, cascade='all, delete-orphan')
    tags = db.relationship('Tag', backref='dono', lazy=True, cascade='all, delete-orphan')
    transacoes_fixas = db.relationship('TransacaoFixa', backref='dono', lazy=True, cascade='all, delete-orphan')
    orcamentos = db.relationship('Orcamento', backref='dono', lazy=True, cascade='all, delete-orphan')
    metas = db.relationship('Meta', backref='dono', lazy=True, cascade='all, delete-orphan')
    cartoes = db.relationship('CartaoCredito', backref='dono', lazy=True, cascade='all, delete-orphan')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Conta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # corrente, poupanca, cartao, dinheiro, investimento
    saldo_inicial = db.Column(db.Float, default=0.0)
    cor = db.Column(db.String(7), default='#7c5cfc')
    icone = db.Column(db.String(30), default='fa-wallet')
    ativo = db.Column(db.Boolean, default=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    transacoes = db.relationship('Transacao', backref='conta', lazy=True)
    transacoes_fixas = db.relationship('TransacaoFixa', backref='conta', lazy=True)

    @property
    def saldo_atual(self):
        receitas = sum(t.valor for t in self.transacoes if t.tipo == 'receita')
        despesas = sum(t.valor for t in self.transacoes if t.tipo == 'despesa')
        return self.saldo_inicial + receitas - despesas

    @property
    def tipo_label(self):
        labels = {
            'corrente': 'Conta Corrente',
            'poupanca': 'Poupança',
            'cartao': 'Cartão de Crédito',
            'dinheiro': 'Dinheiro',
            'investimento': 'Investimento'
        }
        return labels.get(self.tipo, self.tipo)


class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'receita', 'despesa', 'ambos'
    icone = db.Column(db.String(30), default='fa-tag')
    cor = db.Column(db.String(7), default='#7c5cfc')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    transacoes = db.relationship('Transacao', backref='categoria_rel', lazy=True)
    transacoes_fixas = db.relationship('TransacaoFixa', backref='categoria_rel', lazy=True)
    orcamentos = db.relationship('Orcamento', backref='categoria_rel', lazy=True)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(30), nullable=False)
    cor = db.Column(db.String(7), default='#45b7d1')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)


class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    comprovante = db.Column(db.String(200), nullable=True)  # filename of receipt

    tags = db.relationship('Tag', secondary=transacao_tags, lazy='subquery',
                           backref=db.backref('transacoes', lazy=True))

    @property
    def categoria_nome(self):
        if self.categoria_rel:
            return self.categoria_rel.nome
        return 'Sem categoria'

    @property
    def conta_nome(self):
        if self.conta:
            return self.conta.nome
        return 'Sem conta'


class TransacaoFixa(db.Model):
    __tablename__ = 'transacao_fixa'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(10), nullable=False, default='despesa') # 'receita' ou 'despesa'
    dia_vencimento = db.Column(db.Integer, nullable=False)  # 1-31
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Controle de pagamento mensal (JSON: {"2026-02": true, "2026-03": false})
    pagamentos_json = db.Column(db.Text, default='{}')

    @property
    def pagamentos(self):
        try:
            return json.loads(self.pagamentos_json or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def pago_no_mes(self, ano, mes):
        chave = f"{ano}-{mes:02d}"
        return self.pagamentos.get(chave, False)

    def marcar_pago(self, ano, mes):
        p = self.pagamentos
        p[f"{ano}-{mes:02d}"] = True
        self.pagamentos_json = json.dumps(p)

    def desmarcar_pago(self, ano, mes):
        p = self.pagamentos
        p[f"{ano}-{mes:02d}"] = False
        self.pagamentos_json = json.dumps(p)

    @property
    def status_atual(self):
        hoje = date.today()
        if self.pago_no_mes(hoje.year, hoje.month):
            return 'pago'
        if hoje.day > self.dia_vencimento:
            return 'atrasado'
        if hoje.day >= self.dia_vencimento - 3:
            return 'proximo'
        return 'pendente'

    @property
    def categoria_nome(self):
        if self.categoria_rel:
            return self.categoria_rel.nome
        return 'Sem categoria'


class Orcamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    valor_limite = db.Column(db.Float, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    @property
    def valor_gasto(self):
        transacoes = Transacao.query.filter_by(
            usuario_id=self.usuario_id,
            categoria_id=self.categoria_id,
            tipo='despesa'
        ).filter(
            db.extract('month', Transacao.data) == self.mes,
            db.extract('year', Transacao.data) == self.ano
        ).all()
        return sum(t.valor for t in transacoes)

    @property
    def percentual(self):
        if self.valor_limite <= 0:
            return 0
        return min(round((self.valor_gasto / self.valor_limite) * 100, 1), 100)

    @property
    def restante(self):
        return max(self.valor_limite - self.valor_gasto, 0)


class Meta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    valor_alvo = db.Column(db.Float, nullable=False)
    valor_atual = db.Column(db.Float, default=0.0)
    prazo = db.Column(db.Date, nullable=True)
    icone = db.Column(db.String(30), default='fa-bullseye')
    cor = db.Column(db.String(7), default='#7c5cfc')
    concluida = db.Column(db.Boolean, default=False)
    criada_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    @property
    def percentual(self):
        if self.valor_alvo <= 0:
            return 0
        return min(round((self.valor_atual / self.valor_alvo) * 100, 1), 100)

    @property
    def restante(self):
        return max(self.valor_alvo - self.valor_atual, 0)

    @property
    def dias_restantes(self):
        if not self.prazo:
            return None
        delta = self.prazo - date.today()
        return max(delta.days, 0)


class CartaoCredito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    bandeira = db.Column(db.String(30), default='Visa')  # Visa, Mastercard, Elo, etc.
    limite = db.Column(db.Float, nullable=False)
    dia_fechamento = db.Column(db.Integer, nullable=False)  # 1-31
    dia_vencimento = db.Column(db.Integer, nullable=False)  # 1-31
    cor = db.Column(db.String(7), default='#7c5cfc')
    ativo = db.Column(db.Boolean, default=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Transações vinculadas ao cartão via conta
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=True)
    conta_vinculada = db.relationship('Conta', backref='cartao_credito', foreign_keys=[conta_id])

    @property
    def fatura_atual(self):
        """Calcula fatura do mês atual (despesas vinculadas à conta do cartão)."""
        if not self.conta_id:
            return 0
        hoje = date.today()
        transacoes = Transacao.query.filter_by(
            conta_id=self.conta_id,
            tipo='despesa'
        ).filter(
            db.extract('month', Transacao.data) == hoje.month,
            db.extract('year', Transacao.data) == hoje.year
        ).all()
        return sum(t.valor for t in transacoes)

    @property
    def limite_disponivel(self):
        return max(self.limite - self.fatura_atual, 0)

    @property
    def percentual_usado(self):
        if self.limite <= 0:
            return 0
        return min(round((self.fatura_atual / self.limite) * 100, 1), 100)

    @property
    def bandeira_icone(self):
        icones = {
            'Visa': 'fa-cc-visa',
            'Mastercard': 'fa-cc-mastercard',
            'Elo': 'fa-credit-card',
            'Amex': 'fa-cc-amex',
            'Hipercard': 'fa-credit-card',
            'Outro': 'fa-credit-card'
        }
        return icones.get(self.bandeira, 'fa-credit-card')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


# Garantir que as tabelas do banco de dados sejam criadas (útil para o Render / PostgreSQL)
with app.app_context():
    db.create_all()
    # Adicionar colunas novas se não existirem
    try:
        db.session.execute(text('ALTER TABLE usuario ADD COLUMN codigo_verificacao VARCHAR(6)'))
        db.session.execute(text('ALTER TABLE usuario ADD COLUMN codigo_expiracao TIMESTAMP'))
        db.session.commit()
    except Exception:
        db.session.rollback()


# =============================================
# FUNÇÕES DE E-MAIL E AUXILIARES
# =============================================

def enviar_email_verificacao(email_destino, codigo):
    email_user = os.environ.get('EMAIL_USER', 'juninarroba48@gmail.com')
    email_pass = os.environ.get('EMAIL_PASSWORD', 'swoy ujtl ulnl cjme')

    if not email_user or not email_pass:
        print("Erro: Credenciais de e-mail não configuradas (EMAIL_USER ou EMAIL_PASSWORD)")
        return False

    remetente = email_user
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = email_destino
    msg['Subject'] = 'Seu código de verificação - Gestor Financeiro'

    corpo = f"""Olá,

Seu código de verificação para acesso ao Gestor Financeiro é: {codigo}

Este código expira em 10 minutos. Se você não solicitou este acesso, por favor ignore este e-mail.
"""
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        # Define um timeout de 15 segundos para evitar que o worker do Gunicorn/Render trave infinitamente
        servidor = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
        servidor.starttls()
        servidor.login(email_user, email_pass)
        servidor.sendmail(remetente, email_destino, msg.as_string())
        servidor.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

def criar_categorias_padrao(usuario_id):
    """Cria categorias padrão para um novo usuário."""
    categorias_padrao = [
        ('Salário', 'receita', 'fa-money-bill-wave', '#00d68f'),
        ('Freelance', 'receita', 'fa-laptop-code', '#45b7d1'),
        ('Investimentos', 'receita', 'fa-chart-line', '#7c5cfc'),
        ('Outros (Receita)', 'receita', 'fa-plus-circle', '#ffd93d'),
        ('Alimentação', 'despesa', 'fa-utensils', '#ff6b6b'),
        ('Transporte', 'despesa', 'fa-car', '#45b7d1'),
        ('Moradia', 'despesa', 'fa-house', '#7c5cfc'),
        ('Saúde', 'despesa', 'fa-heart-pulse', '#ff4757'),
        ('Educação', 'despesa', 'fa-graduation-cap', '#00d68f'),
        ('Lazer', 'despesa', 'fa-gamepad', '#f093fb'),
        ('Roupas', 'despesa', 'fa-shirt', '#ff8a5c'),
        ('Contas (Luz, Água)', 'despesa', 'fa-file-invoice', '#ffd93d'),
        ('Assinaturas', 'despesa', 'fa-tv', '#6c5ce7'),
        ('Outros (Despesa)', 'despesa', 'fa-receipt', '#a0a3bd'),
    ]
    for nome, tipo, icone, cor in categorias_padrao:
        cat = Categoria(nome=nome, tipo=tipo, icone=icone, cor=cor, usuario_id=usuario_id)
        db.session.add(cat)


def criar_conta_padrao(usuario_id):
    """Cria conta padrão 'Carteira' para um novo usuário."""
    conta = Conta(
        nome='Carteira',
        tipo='dinheiro',
        saldo_inicial=0.0,
        cor='#00d68f',
        icone='fa-wallet',
        usuario_id=usuario_id
    )
    db.session.add(conta)


# =============================================
# ROTAS PÚBLICAS
# =============================================

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Email ou senha incorretos.', 'error')

    return render_template('login.html')


@app.route('/api/login/request_code', methods=['POST'])
def api_request_code():
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({'status': 'error', 'message': 'E-mail não fornecido'}), 400
        
        email = data['email'].strip()
        usuario = Usuario.query.filter_by(email=email).first()
        
        if not usuario:
            return jsonify({'status': 'error', 'message': 'E-mail não encontrado no sistema'}), 404
        
        codigo = str(random.randint(100000, 999999))
        expiracao = datetime.utcnow() + timedelta(minutes=10)
        
        usuario.codigo_verificacao = codigo
        usuario.codigo_expiracao = expiracao
        db.session.commit()
        
        sucesso = enviar_email_verificacao(usuario.email, codigo)
        if sucesso:
            return jsonify({'status': 'success', 'message': 'Código enviado com sucesso'})
        else:
            return jsonify({'status': 'error', 'message': 'Erro ao enviar o e-mail. Verifique as configurações.'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Erro interno: {str(e)}'}), 500


@app.route('/api/login/verify_code', methods=['POST'])
def api_verify_code():
    data = request.get_json()
    if not data or 'email' not in data or 'codigo' not in data:
        return jsonify({'status': 'error', 'message': 'E-mail ou código não fornecido'}), 400
    
    email = data['email'].strip()
    codigo = data['codigo'].strip()
    
    usuario = Usuario.query.filter_by(email=email).first()
    
    if not usuario:
        return jsonify({'status': 'error', 'message': 'Usuário não encontrado'}), 404
        
    if not usuario.codigo_verificacao or not usuario.codigo_expiracao:
        return jsonify({'status': 'error', 'message': 'Nenhum código foi solicitado'}), 400
        
    if usuario.codigo_verificacao != codigo:
        return jsonify({'status': 'error', 'message': 'Código incorreto'}), 400
        
    if datetime.utcnow() > usuario.codigo_expiracao:
        return jsonify({'status': 'error', 'message': 'Código expirado. Solicite um novo.'}), 400
        
    # Sucesso
    usuario.codigo_verificacao = None
    usuario.codigo_expiracao = None
    db.session.commit()
    
    login_user(usuario)
    return jsonify({'status': 'success', 'message': 'Login realizado com sucesso'})


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')

        if not nome or not email or not senha:
            flash('Preencha todos os campos.', 'error')
            return render_template('cadastro.html')

        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'error')
            return render_template('cadastro.html')

        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'error')
            return render_template('cadastro.html')

        novo_usuario = Usuario(nome=nome, email=email)
        novo_usuario.set_senha(senha)

        try:
            db.session.add(novo_usuario)
            db.session.flush()  # get the ID before creating defaults

            criar_categorias_padrao(novo_usuario.id)
            criar_conta_padrao(novo_usuario.id)

            db.session.commit()
            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except Exception:
            db.session.rollback()
            flash('Erro ao criar conta. Tente novamente.', 'error')

    return render_template('cadastro.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('home'))


# =============================================
# DASHBOARD
# =============================================

@app.route('/dashboard')
@login_required
def dashboard():
    mes_filtro = request.args.get('mes', '')
    ano_filtro = request.args.get('ano', '')
    categoria_filtro = request.args.get('categoria', '')
    conta_filtro = request.args.get('conta', '')

    query = Transacao.query.filter_by(usuario_id=current_user.id)

    if mes_filtro and ano_filtro:
        try:
            query = query.filter(
                db.extract('month', Transacao.data) == int(mes_filtro),
                db.extract('year', Transacao.data) == int(ano_filtro)
            )
        except ValueError:
            pass
    elif ano_filtro:
        try:
            query = query.filter(db.extract('year', Transacao.data) == int(ano_filtro))
        except ValueError:
            pass

    if categoria_filtro:
        try:
            query = query.filter_by(categoria_id=int(categoria_filtro))
        except ValueError:
            pass

    if conta_filtro:
        try:
            query = query.filter_by(conta_id=int(conta_filtro))
        except ValueError:
            pass

    transacoes = query.order_by(Transacao.data.desc()).all()

    total_receitas = sum(t.valor for t in transacoes if t.tipo == 'receita')
    total_despesas = sum(t.valor for t in transacoes if t.tipo == 'despesa')
    saldo = total_receitas - total_despesas

    categorias = Categoria.query.filter_by(usuario_id=current_user.id).order_by(Categoria.nome).all()
    contas = Conta.query.filter_by(usuario_id=current_user.id, ativo=True).all()
    tags = Tag.query.filter_by(usuario_id=current_user.id).order_by(Tag.nome).all()

    # Gráfico de pizza (despesas por categoria)
    categorias_grafico = {}
    for t in transacoes:
        if t.tipo == 'despesa':
            nome = t.categoria_nome
            categorias_grafico[nome] = categorias_grafico.get(nome, 0) + t.valor

    # Anos para filtro
    todas = Transacao.query.filter_by(usuario_id=current_user.id).all()
    anos = sorted(set(t.data.year for t in todas), reverse=True) or [datetime.now().year]

    # Orçamentos do mês atual
    hoje = date.today()
    orcamentos = Orcamento.query.filter_by(
        usuario_id=current_user.id,
        mes=hoje.month,
        ano=hoje.year
    ).all()

    # Despesas fixas pendentes
    transacoes_fixas = TransacaoFixa.query.filter_by(
        usuario_id=current_user.id,
        ativo=True
    ).all()
    pendentes = [d for d in transacoes_fixas if d.status_atual in ('pendente', 'proximo', 'atrasado')]

    # Saldo total de todas as contas
    saldo_total = sum(c.saldo_atual for c in contas)

    return render_template('dashboard.html',
                           transacoes=transacoes,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           saldo=saldo,
                           saldo_total=saldo_total,
                           categorias=categorias,
                           contas=contas,
                           tags=tags,
                           categorias_grafico=categorias_grafico,
                           anos=anos,
                           mes_filtro=mes_filtro,
                           ano_filtro=ano_filtro,
                           categoria_filtro=categoria_filtro,
                           conta_filtro=conta_filtro,
                           orcamentos=orcamentos,
                           pendentes=pendentes)


# =============================================
# TRANSAÇÕES CRUD
# =============================================

@app.route('/transacao/nova', methods=['POST'])
@login_required
def nova_transacao():
    tipo = request.form.get('tipo', '').strip().lower()
    valor = request.form.get('valor', '')
    categoria_id = request.form.get('categoria_id', '')
    conta_id = request.form.get('conta_id', '')
    descricao = request.form.get('descricao', '').strip()
    data_str = request.form.get('data', '')
    tag_ids = request.form.getlist('tags')

    if tipo not in ('receita', 'despesa'):
        flash('Tipo de transação inválido.', 'error')
        return redirect(url_for('dashboard'))

    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Valor inválido.', 'error')
        return redirect(url_for('dashboard'))

    data = datetime.utcnow()
    if data_str:
        try:
            data = datetime.strptime(data_str, '%Y-%m-%d')
        except ValueError:
            pass

    transacao = Transacao(
        tipo=tipo,
        valor=valor,
        descricao=descricao,
        data=data,
        usuario_id=current_user.id,
        categoria_id=int(categoria_id) if categoria_id else None,
        conta_id=int(conta_id) if conta_id else None
    )

    # Adicionar tags
    if tag_ids:
        tags = Tag.query.filter(Tag.id.in_(tag_ids), Tag.usuario_id == current_user.id).all()
        transacao.tags = tags

    db.session.add(transacao)
    db.session.commit()
    flash(f'{"Receita" if tipo == "receita" else "Despesa"} adicionada!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transacao/editar/<int:id>', methods=['POST'])
@login_required
def editar_transacao(id):
    transacao = Transacao.query.get_or_404(id)
    if transacao.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))

    transacao.tipo = request.form.get('tipo', transacao.tipo).strip().lower()
    transacao.descricao = request.form.get('descricao', '').strip()

    categoria_id = request.form.get('categoria_id', '')
    transacao.categoria_id = int(categoria_id) if categoria_id else None

    conta_id = request.form.get('conta_id', '')
    transacao.conta_id = int(conta_id) if conta_id else None

    try:
        transacao.valor = float(request.form.get('valor', transacao.valor))
    except (ValueError, TypeError):
        flash('Valor inválido.', 'error')
        return redirect(url_for('dashboard'))

    data_str = request.form.get('data', '')
    if data_str:
        try:
            transacao.data = datetime.strptime(data_str, '%Y-%m-%d')
        except ValueError:
            pass

    tag_ids = request.form.getlist('tags')
    if tag_ids:
        tags = Tag.query.filter(Tag.id.in_(tag_ids), Tag.usuario_id == current_user.id).all()
        transacao.tags = tags
    else:
        transacao.tags = []

    db.session.commit()
    flash('Transação atualizada!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transacao/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_transacao(id):
    transacao = Transacao.query.get_or_404(id)
    if transacao.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))

    db.session.delete(transacao)
    db.session.commit()
    flash('Transação excluída!', 'success')
    return redirect(url_for('dashboard'))


# =============================================
# CONTAS CRUD
# =============================================

@app.route('/contas')
@login_required
def contas():
    contas = Conta.query.filter_by(usuario_id=current_user.id).all()
    return render_template('contas.html', contas=contas)


@app.route('/conta/nova', methods=['POST'])
@login_required
def nova_conta():
    nome = request.form.get('nome', '').strip()
    tipo = request.form.get('tipo', 'corrente')
    saldo_inicial = request.form.get('saldo_inicial', '0')
    cor = request.form.get('cor', '#7c5cfc')
    icone = request.form.get('icone', 'fa-wallet')

    if not nome:
        flash('Informe o nome da conta.', 'error')
        return redirect(url_for('contas'))

    try:
        saldo_inicial = float(saldo_inicial)
    except (ValueError, TypeError):
        saldo_inicial = 0.0

    conta = Conta(nome=nome, tipo=tipo, saldo_inicial=saldo_inicial,
                  cor=cor, icone=icone, usuario_id=current_user.id)
    db.session.add(conta)
    db.session.commit()
    flash('Conta criada!', 'success')
    return redirect(url_for('contas'))


@app.route('/conta/editar/<int:id>', methods=['POST'])
@login_required
def editar_conta(id):
    conta = Conta.query.get_or_404(id)
    if conta.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('contas'))

    conta.nome = request.form.get('nome', conta.nome).strip()
    conta.tipo = request.form.get('tipo', conta.tipo)
    conta.cor = request.form.get('cor', conta.cor)
    conta.icone = request.form.get('icone', conta.icone)

    try:
        conta.saldo_inicial = float(request.form.get('saldo_inicial', conta.saldo_inicial))
    except (ValueError, TypeError):
        pass

    db.session.commit()
    flash('Conta atualizada!', 'success')
    return redirect(url_for('contas'))


@app.route('/conta/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_conta(id):
    conta = Conta.query.get_or_404(id)
    if conta.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('contas'))

    db.session.delete(conta)
    db.session.commit()
    flash('Conta excluída!', 'success')
    return redirect(url_for('contas'))


# =============================================
# CATEGORIAS CRUD
# =============================================

@app.route('/categorias')
@login_required
def categorias():
    cats = Categoria.query.filter_by(usuario_id=current_user.id).order_by(Categoria.tipo, Categoria.nome).all()
    return render_template('categorias.html', categorias=cats)


@app.route('/categoria/nova', methods=['POST'])
@login_required
def nova_categoria():
    nome = request.form.get('nome', '').strip()
    tipo = request.form.get('tipo', 'despesa')
    icone = request.form.get('icone', 'fa-tag')
    cor = request.form.get('cor', '#7c5cfc')

    if not nome:
        flash('Informe o nome da categoria.', 'error')
        return redirect(url_for('categorias'))

    cat = Categoria(nome=nome, tipo=tipo, icone=icone, cor=cor, usuario_id=current_user.id)
    db.session.add(cat)
    db.session.commit()
    flash('Categoria criada!', 'success')
    return redirect(url_for('categorias'))


@app.route('/categoria/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_categoria(id):
    cat = Categoria.query.get_or_404(id)
    if cat.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('categorias'))

    db.session.delete(cat)
    db.session.commit()
    flash('Categoria excluída!', 'success')
    return redirect(url_for('categorias'))


# =============================================
# TAGS CRUD
# =============================================

@app.route('/tag/nova', methods=['POST'])
@login_required
def nova_tag():
    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#45b7d1')

    if not nome:
        flash('Informe o nome da tag.', 'error')
        return redirect(url_for('categorias'))

    tag = Tag(nome=nome, cor=cor, usuario_id=current_user.id)
    db.session.add(tag)
    db.session.commit()
    flash('Tag criada!', 'success')
    return redirect(url_for('categorias'))


@app.route('/tag/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_tag(id):
    tag = Tag.query.get_or_404(id)
    if tag.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('categorias'))

    db.session.delete(tag)
    db.session.commit()
    flash('Tag excluída!', 'success')
    return redirect(url_for('categorias'))


# =============================================
# =============================================
# TRANSAÇÕES FIXAS
# =============================================

@app.route('/transacoes-fixas/<tipo>')
@login_required
def transacoes_fixas(tipo):
    if tipo not in ('receita', 'despesa'):
        tipo = 'despesa'
        
    transacoes = TransacaoFixa.query.filter_by(usuario_id=current_user.id, tipo=tipo).order_by(TransacaoFixa.dia_vencimento).all()
    categorias = Categoria.query.filter_by(usuario_id=current_user.id, tipo=tipo).all()
    contas = Conta.query.filter_by(usuario_id=current_user.id, ativo=True).all()
    hoje = date.today()

    total_fixo = sum(d.valor for d in transacoes if d.ativo)
    total_pago = sum(d.valor for d in transacoes if d.ativo and d.pago_no_mes(hoje.year, hoje.month))
    total_pendente = total_fixo - total_pago

    return render_template('transacoes_fixas.html',
                           despesas=transacoes,
                           categorias=categorias,
                           contas=contas,
                           hoje=hoje,
                           tipo=tipo,
                           total_fixo=total_fixo,
                           total_pago=total_pago,
                           total_pendente=total_pendente)


@app.route('/transacao-fixa/nova', methods=['POST'])
@login_required
def nova_transacao_fixa():
    nome = request.form.get('nome', '').strip()
    valor = request.form.get('valor', '')
    dia = request.form.get('dia_vencimento', '')
    categoria_id = request.form.get('categoria_id', '')
    conta_id = request.form.get('conta_id', '')
    tipo = request.form.get('tipo', 'despesa')

    target_url = url_for('transacoes_fixas', tipo=tipo)

    if not nome:
        flash('Informe o nome.', 'error')
        return redirect(target_url)

    try:
        valor = float(valor)
        dia = int(dia)
        if dia < 1 or dia > 31:
            raise ValueError
    except (ValueError, TypeError):
        flash('Valores inválidos.', 'error')
        return redirect(target_url)

    transacao_fixa = TransacaoFixa(
        nome=nome, valor=valor, dia_vencimento=dia, tipo=tipo,
        categoria_id=int(categoria_id) if categoria_id else None,
        conta_id=int(conta_id) if conta_id else None,
        usuario_id=current_user.id
    )
    db.session.add(transacao_fixa)
    db.session.commit()
    flash('Transação fixa criada!', 'success')
    return redirect(target_url)


@app.route('/transacao-fixa/pagar/<int:id>', methods=['POST'])
@login_required
def pagar_transacao_fixa(id):
    transacao_fixa = TransacaoFixa.query.get_or_404(id)
    if transacao_fixa.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))

    target_url = url_for('transacoes_fixas', tipo=transacao_fixa.tipo)

    hoje = date.today()
    transacao_fixa.marcar_pago(hoje.year, hoje.month)

    # Cria transação automática
    transacao = Transacao(
        tipo=transacao_fixa.tipo,
        valor=transacao_fixa.valor,
        descricao=f'Fixo: {transacao_fixa.nome}',
        data=datetime.now(),
        usuario_id=current_user.id,
        categoria_id=transacao_fixa.categoria_id,
        conta_id=transacao_fixa.conta_id
    )
    db.session.add(transacao)
    db.session.commit()
    flash(f'{transacao_fixa.nome} contabilizada neste mês!', 'success')
    return redirect(target_url)


@app.route('/transacao-fixa/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_transacao_fixa(id):
    transacao_fixa = TransacaoFixa.query.get_or_404(id)
    tipo = transacao_fixa.tipo
    
    if transacao_fixa.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))

    db.session.delete(transacao_fixa)
    db.session.commit()
    flash('Transação fixa excluída!', 'success')
    return redirect(url_for('transacoes_fixas', tipo=tipo))


# =============================================
# ORÇAMENTOS
# =============================================

@app.route('/orcamentos')
@login_required
def orcamentos():
    hoje = date.today()
    mes = request.args.get('mes', hoje.month, type=int)
    ano = request.args.get('ano', hoje.year, type=int)

    orcs = Orcamento.query.filter_by(
        usuario_id=current_user.id, mes=mes, ano=ano
    ).all()
    categorias = Categoria.query.filter_by(usuario_id=current_user.id, tipo='despesa').all()

    # Categorias que já têm orçamento
    cats_com_orc = {o.categoria_id for o in orcs}
    cats_disponiveis = [c for c in categorias if c.id not in cats_com_orc]

    total_limite = sum(o.valor_limite for o in orcs)
    total_gasto = sum(o.valor_gasto for o in orcs)

    return render_template('orcamentos.html',
                           orcamentos=orcs,
                           categorias=cats_disponiveis,
                           mes=mes, ano=ano,
                           total_limite=total_limite,
                           total_gasto=total_gasto)


@app.route('/orcamento/novo', methods=['POST'])
@login_required
def novo_orcamento():
    categoria_id = request.form.get('categoria_id', '')
    valor_limite = request.form.get('valor_limite', '')
    mes = request.form.get('mes', '')
    ano = request.form.get('ano', '')

    try:
        orc = Orcamento(
            categoria_id=int(categoria_id),
            valor_limite=float(valor_limite),
            mes=int(mes),
            ano=int(ano),
            usuario_id=current_user.id
        )
        db.session.add(orc)
        db.session.commit()
        flash('Orçamento criado!', 'success')
    except (ValueError, TypeError):
        flash('Valores inválidos.', 'error')

    return redirect(url_for('orcamentos'))


@app.route('/orcamento/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_orcamento(id):
    orc = Orcamento.query.get_or_404(id)
    if orc.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('orcamentos'))

    db.session.delete(orc)
    db.session.commit()
    flash('Orçamento excluído!', 'success')
    return redirect(url_for('orcamentos'))


# =============================================
# METAS FINANCEIRAS
# =============================================

@app.route('/metas')
@login_required
def metas():
    metas_ativas = Meta.query.filter_by(usuario_id=current_user.id, concluida=False).order_by(Meta.prazo).all()
    metas_concluidas = Meta.query.filter_by(usuario_id=current_user.id, concluida=True).all()

    total_alvo = sum(m.valor_alvo for m in metas_ativas)
    total_acumulado = sum(m.valor_atual for m in metas_ativas)

    return render_template('metas.html',
                           metas_ativas=metas_ativas,
                           metas_concluidas=metas_concluidas,
                           total_alvo=total_alvo,
                           total_acumulado=total_acumulado)


@app.route('/meta/nova', methods=['POST'])
@login_required
def nova_meta():
    nome = request.form.get('nome', '').strip()
    descricao = request.form.get('descricao', '').strip()
    valor_alvo = request.form.get('valor_alvo', '')
    prazo_str = request.form.get('prazo', '')
    icone = request.form.get('icone', 'fa-bullseye')
    cor = request.form.get('cor', '#7c5cfc')

    if not nome:
        flash('Informe o nome da meta.', 'error')
        return redirect(url_for('metas'))

    try:
        valor_alvo = float(valor_alvo)
        if valor_alvo <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Valor alvo inválido.', 'error')
        return redirect(url_for('metas'))

    prazo = None
    if prazo_str:
        try:
            prazo = datetime.strptime(prazo_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    meta = Meta(
        nome=nome, descricao=descricao, valor_alvo=valor_alvo,
        prazo=prazo, icone=icone, cor=cor, usuario_id=current_user.id
    )
    db.session.add(meta)
    db.session.commit()
    flash('Meta criada!', 'success')
    return redirect(url_for('metas'))


@app.route('/meta/depositar/<int:id>', methods=['POST'])
@login_required
def depositar_meta(id):
    meta = Meta.query.get_or_404(id)
    if meta.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('metas'))

    valor = request.form.get('valor', '')
    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Valor inválido.', 'error')
        return redirect(url_for('metas'))

    meta.valor_atual = min(meta.valor_atual + valor, meta.valor_alvo)
    if meta.valor_atual >= meta.valor_alvo:
        meta.concluida = True
        flash(f'🎉 Meta "{meta.nome}" concluída!', 'success')
    else:
        flash(f'Depósito de R$ {valor:.2f} realizado!', 'success')

    db.session.commit()
    return redirect(url_for('metas'))


@app.route('/meta/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_meta(id):
    meta = Meta.query.get_or_404(id)
    if meta.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('metas'))

    db.session.delete(meta)
    db.session.commit()
    flash('Meta excluída!', 'success')
    return redirect(url_for('metas'))


# =============================================
# CARTÕES DE CRÉDITO
# =============================================

@app.route('/cartoes')
@login_required
def cartoes():
    cards = CartaoCredito.query.filter_by(usuario_id=current_user.id).all()
    contas = Conta.query.filter_by(usuario_id=current_user.id, ativo=True).all()
    return render_template('cartoes.html', cartoes=cards, contas=contas)


@app.route('/cartao/novo', methods=['POST'])
@login_required
def novo_cartao():
    nome = request.form.get('nome', '').strip()
    bandeira = request.form.get('bandeira', 'Visa')
    limite = request.form.get('limite', '')
    dia_fechamento = request.form.get('dia_fechamento', '')
    dia_vencimento = request.form.get('dia_vencimento', '')
    cor = request.form.get('cor', '#7c5cfc')
    conta_id = request.form.get('conta_id', '')

    if not nome:
        flash('Informe o nome do cartão.', 'error')
        return redirect(url_for('cartoes'))

    try:
        limite = float(limite)
        dia_fechamento = int(dia_fechamento)
        dia_vencimento = int(dia_vencimento)
    except (ValueError, TypeError):
        flash('Valores inválidos.', 'error')
        return redirect(url_for('cartoes'))

    # Cria uma conta vinculada ao cartão automaticamente
    conta_cartao = Conta(
        nome=f'Cartão {nome}',
        tipo='cartao',
        saldo_inicial=0.0,
        cor=cor,
        icone='fa-credit-card',
        usuario_id=current_user.id
    )
    db.session.add(conta_cartao)
    db.session.flush()

    cartao = CartaoCredito(
        nome=nome, bandeira=bandeira, limite=limite,
        dia_fechamento=dia_fechamento, dia_vencimento=dia_vencimento,
        cor=cor, conta_id=conta_cartao.id, usuario_id=current_user.id
    )
    db.session.add(cartao)
    db.session.commit()
    flash(f'Cartão {nome} cadastrado!', 'success')
    return redirect(url_for('cartoes'))


@app.route('/cartao/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_cartao(id):
    cartao = CartaoCredito.query.get_or_404(id)
    if cartao.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('cartoes'))

    db.session.delete(cartao)
    db.session.commit()
    flash('Cartão excluído!', 'success')
    return redirect(url_for('cartoes'))


# =============================================
# RELATÓRIOS
# =============================================

@app.route('/relatorios')
@login_required
def relatorios():
    hoje = date.today()
    ano = request.args.get('ano', hoje.year, type=int)

    # Dados mensais do ano selecionado
    meses_dados = []
    for m in range(1, 13):
        transacoes_mes = Transacao.query.filter_by(
            usuario_id=current_user.id
        ).filter(
            db.extract('month', Transacao.data) == m,
            db.extract('year', Transacao.data) == ano
        ).all()

        receitas = sum(t.valor for t in transacoes_mes if t.tipo == 'receita')
        despesas = sum(t.valor for t in transacoes_mes if t.tipo == 'despesa')
        meses_dados.append({
            'mes': m,
            'nome': ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][m-1],
            'receitas': receitas,
            'despesas': despesas,
            'saldo': receitas - despesas
        })

    # Totais do ano
    total_receitas_ano = sum(m['receitas'] for m in meses_dados)
    total_despesas_ano = sum(m['despesas'] for m in meses_dados)

    # Top 5 categorias de despesa do ano
    todas_despesas = Transacao.query.filter_by(
        usuario_id=current_user.id, tipo='despesa'
    ).filter(
        db.extract('year', Transacao.data) == ano
    ).all()

    cat_totals = {}
    for t in todas_despesas:
        nome = t.categoria_nome
        cat_totals[nome] = cat_totals.get(nome, 0) + t.valor
    top_categorias = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:8]

    # Top 5 categorias de receita do ano
    todas_receitas = Transacao.query.filter_by(
        usuario_id=current_user.id, tipo='receita'
    ).filter(
        db.extract('year', Transacao.data) == ano
    ).all()

    cat_receitas = {}
    for t in todas_receitas:
        nome = t.categoria_nome
        cat_receitas[nome] = cat_receitas.get(nome, 0) + t.valor
    top_receitas = sorted(cat_receitas.items(), key=lambda x: x[1], reverse=True)[:8]

    # Evolução do saldo acumulado
    saldo_acumulado = []
    acum = 0
    for m in meses_dados:
        acum += m['saldo']
        saldo_acumulado.append(round(acum, 2))

    # Anos disponíveis
    todas = Transacao.query.filter_by(usuario_id=current_user.id).all()
    anos = sorted(set(t.data.year for t in todas), reverse=True) or [hoje.year]

    return render_template('relatorios.html',
                           meses_dados=meses_dados,
                           total_receitas_ano=total_receitas_ano,
                           total_despesas_ano=total_despesas_ano,
                           top_categorias=top_categorias,
                           top_receitas=top_receitas,
                           saldo_acumulado=saldo_acumulado,
                           ano=ano, anos=anos)


# =============================================
# CALENDÁRIO FINANCEIRO
# =============================================

@app.route('/calendario')
@login_required
def calendario():
    hoje = date.today()
    mes = request.args.get('mes', hoje.month, type=int)
    ano = request.args.get('ano', hoje.year, type=int)

    # Dias do mês
    primeiro_dia_semana, dias_no_mes = cal_module.monthrange(ano, mes)

    # Transações do mês agrupadas por dia
    transacoes_mes = Transacao.query.filter_by(
        usuario_id=current_user.id
    ).filter(
        db.extract('month', Transacao.data) == mes,
        db.extract('year', Transacao.data) == ano
    ).order_by(Transacao.data).all()

    dias = {}
    for t in transacoes_mes:
        dia = t.data.day
        if dia not in dias:
            dias[dia] = {'receitas': 0, 'despesas': 0, 'transacoes': []}
        if t.tipo == 'receita':
            dias[dia]['receitas'] += t.valor
        else:
            dias[dia]['despesas'] += t.valor
        dias[dia]['transacoes'].append(t)

    # Despesas fixas do mês
    transacoes_fixas = TransacaoFixa.query.filter_by(
        usuario_id=current_user.id, ativo=True
    ).all()
    vencimentos = {d.dia_vencimento: d for d in transacoes_fixas}

    nome_mes = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'][mes-1]

    # Navegação
    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1
    mes_prox = mes + 1 if mes < 12 else 1
    ano_prox = ano if mes < 12 else ano + 1

    return render_template('calendario.html',
                           dias=dias, vencimentos=vencimentos,
                           dias_no_mes=dias_no_mes,
                           primeiro_dia_semana=primeiro_dia_semana,
                           mes=mes, ano=ano, nome_mes=nome_mes,
                           mes_ant=mes_ant, ano_ant=ano_ant,
                           mes_prox=mes_prox, ano_prox=ano_prox,
                           hoje=hoje)


# =============================================
# BUSCA GLOBAL
# =============================================

@app.route('/busca')
@login_required
def busca():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    valor_min = request.args.get('valor_min', '')
    valor_max = request.args.get('valor_max', '')

    resultados = []
    total = 0

    if q or tipo or data_inicio or data_fim or valor_min or valor_max:
        query = Transacao.query.filter_by(usuario_id=current_user.id)

        if q:
            query = query.filter(
                db.or_(
                    Transacao.descricao.ilike(f'%{q}%'),
                )
            )

        if tipo and tipo in ('receita', 'despesa'):
            query = query.filter_by(tipo=tipo)

        if data_inicio:
            try:
                dt = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(Transacao.data >= dt)
            except ValueError:
                pass

        if data_fim:
            try:
                dt = datetime.strptime(data_fim, '%Y-%m-%d')
                query = query.filter(Transacao.data <= dt)
            except ValueError:
                pass

        if valor_min:
            try:
                query = query.filter(Transacao.valor >= float(valor_min))
            except ValueError:
                pass

        if valor_max:
            try:
                query = query.filter(Transacao.valor <= float(valor_max))
            except ValueError:
                pass

        resultados = query.order_by(Transacao.data.desc()).limit(100).all()
        total = len(resultados)

    return render_template('busca.html',
                           resultados=resultados, total=total,
                           q=q, tipo=tipo,
                           data_inicio=data_inicio, data_fim=data_fim,
                           valor_min=valor_min, valor_max=valor_max)


# =============================================
# PERFIL DO USUÁRIO
# =============================================

@app.route('/perfil')
@login_required
def perfil():
    total_transacoes = Transacao.query.filter_by(usuario_id=current_user.id).count()
    total_receitas = sum(t.valor for t in Transacao.query.filter_by(usuario_id=current_user.id, tipo='receita').all())
    total_despesas = sum(t.valor for t in Transacao.query.filter_by(usuario_id=current_user.id, tipo='despesa').all())
    total_contas = Conta.query.filter_by(usuario_id=current_user.id).count()
    metas_concluidas = Meta.query.filter_by(usuario_id=current_user.id, concluida=True).count()

    return render_template('perfil.html',
                           total_transacoes=total_transacoes,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           total_contas=total_contas,
                           metas_concluidas=metas_concluidas)


@app.route('/perfil/editar', methods=['POST'])
@login_required
def editar_perfil():
    nome = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip()

    if not nome or not email:
        flash('Nome e email são obrigatórios.', 'error')
        return redirect(url_for('perfil'))

    # Check email unique
    if email != current_user.email:
        exists = Usuario.query.filter_by(email=email).first()
        if exists:
            flash('Este email já está em uso.', 'error')
            return redirect(url_for('perfil'))

    current_user.nome = nome
    current_user.email = email
    db.session.commit()
    flash('Perfil atualizado!', 'success')
    return redirect(url_for('perfil'))


@app.route('/perfil/senha', methods=['POST'])
@login_required
def alterar_senha():
    senha_atual = request.form.get('senha_atual', '')
    nova_senha = request.form.get('nova_senha', '')
    confirmar = request.form.get('confirmar_senha', '')

    if not current_user.check_senha(senha_atual):
        flash('Senha atual incorreta.', 'error')
        return redirect(url_for('perfil'))

    if len(nova_senha) < 6:
        flash('Nova senha deve ter pelo menos 6 caracteres.', 'error')
        return redirect(url_for('perfil'))

    if nova_senha != confirmar:
        flash('Confirmação de senha não confere.', 'error')
        return redirect(url_for('perfil'))

    current_user.set_senha(nova_senha)
    db.session.commit()
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('perfil'))


# =============================================
# TEMA
# =============================================

@app.route('/tema/toggle', methods=['POST'])
@login_required
def toggle_tema():
    current_user.tema = 'light' if current_user.tema == 'dark' else 'dark'
    db.session.commit()
    return jsonify({'tema': current_user.tema})


# =============================================
# EXPORTAR CSV
# =============================================

@app.route('/exportar/csv')
@login_required
def exportar_csv():
    mes = request.args.get('mes', None, type=int)
    ano = request.args.get('ano', None, type=int)

    query = Transacao.query.filter_by(usuario_id=current_user.id)
    if mes and ano:
        query = query.filter(
            db.extract('month', Transacao.data) == mes,
            db.extract('year', Transacao.data) == ano
        )
    elif ano:
        query = query.filter(db.extract('year', Transacao.data) == ano)

    transacoes = query.order_by(Transacao.data.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Tipo', 'Valor', 'Categoria', 'Conta', 'Descrição'])

    for t in transacoes:
        writer.writerow([
            t.data.strftime('%d/%m/%Y') if t.data else '',
            t.tipo,
            f'{t.valor:.2f}',
            t.categoria_nome,
            t.conta_rel.nome if t.conta_rel else '',
            t.descricao or ''
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    filename = f'transacoes_{ano or "todos"}'
    if mes:
        filename += f'_{mes:02d}'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}.csv'
    return response


# =============================================
# UPLOAD DE COMPROVANTES
# =============================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/transacao/comprovante/<int:id>', methods=['POST'])
@login_required
def upload_comprovante(id):
    transacao = Transacao.query.get_or_404(id)
    if transacao.usuario_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))

    if 'comprovante' not in request.files:
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('dashboard'))

    file = request.files['comprovante']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('dashboard'))

    if file and allowed_file(file.filename):
        try:
            # Enviar para o Cloudinary (detectando o tipo do arquivo automaticamente)
            upload_result = cloudinary.uploader.upload(file, resource_type='auto')
            
            # Pegar a URL segura que o Cloudinary retornou
            url_comprovante = upload_result.get('secure_url')
            
            transacao.comprovante = url_comprovante
            db.session.commit()
            flash('Comprovante enviado!', 'success')
        except Exception as e:
            flash(f'Erro no upload: {str(e)}', 'error')
    else:
        flash('Tipo de arquivo não permitido. Use: PNG, JPG, PDF, WebP.', 'error')

    return redirect(url_for('dashboard'))


# =============================================
# TEMPLATE FILTERS
# =============================================

@app.template_filter('brl')
def format_brl(value):
    try:
        return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return "R$ 0,00"


@app.template_filter('data_br')
def format_data_br(value):
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    return value


# =============================================
# INICIALIZAÇÃO
# =============================================

if __name__ == '__main__':
    app.run(debug=True)
