from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import calendar as cal_module
import json
import csv
import io
import uuid
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__)

# Configurações locais
app.config['SECRET_KEY'] = 'gestor-financeiro-local-key-2026'

# Configuração do Cloudinary
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
  api_key = os.environ.get('CLOUDINARY_API_KEY', '439547935185919'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET', '3lPycV2JNER-wcV96W1l1sC4vmg')
)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# =============================================
# MODELOS
# =============================================

# Tabela associativa Tag <-> Transacao
transacao_tags = db.Table('transacao_tags',
    db.Column('transacao_id', db.Integer, db.ForeignKey('transacao.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tema = db.Column(db.String(10), default='dark')  # 'dark' ou 'light'
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    transacoes = db.relationship('Transacao', backref='dono', lazy=True, cascade='all, delete-orphan')
    contas = db.relationship('Conta', backref='dono', lazy=True, cascade='all, delete-orphan')
    categorias = db.relationship('Categoria', backref='dono', lazy=True, cascade='all, delete-orphan')
    tags = db.relationship('Tag', backref='dono', lazy=True, cascade='all, delete-orphan')
    transacoes_fixas = db.relationship('TransacaoFixa', backref='dono', lazy=True, cascade='all, delete-orphan')
    orcamentos = db.relationship('Orcamento', backref='dono', lazy=True, cascade='all, delete-orphan')
    metas = db.relationship('Meta', backref='dono', lazy=True, cascade='all, delete-orphan')
    cartoes = db.relationship('CartaoCredito', backref='dono', lazy=True, cascade='all, delete-orphan')


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

    # Parcelas
    parcela_grupo_id = db.Column(db.String(36), nullable=True)  # UUID do grupo
    parcela_num = db.Column(db.Integer, nullable=True)  # ex: 3
    parcela_total = db.Column(db.Integer, nullable=True)  # ex: 12

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

    @property
    def parcela_label(self):
        if self.parcela_num and self.parcela_total:
            return f'{self.parcela_num}/{self.parcela_total}'
        return None


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

    depositos = db.relationship('DepositoMeta', backref='meta', lazy=True,
                                cascade='all, delete-orphan', order_by='DepositoMeta.data.desc()')

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


class DepositoMeta(db.Model):
    __tablename__ = 'deposito_meta'
    id = db.Column(db.Integer, primary_key=True)
    meta_id = db.Column(db.Integer, db.ForeignKey('meta.id'), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    descricao = db.Column(db.String(200), nullable=True)


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


# Criar tabelas do banco de dados
with app.app_context():
    db.create_all()


# =============================================
# HELPER: USUÁRIO ÚNICO LOCAL
# =============================================

def get_user():
    """Retorna o usuário único local, criando-o automaticamente se não existir."""
    usuario = Usuario.query.first()
    if not usuario:
        usuario = Usuario(nome='Usuário')
        db.session.add(usuario)
        db.session.flush()

        # Criar categorias padrão
        criar_categorias_padrao(usuario.id)
        criar_conta_padrao(usuario.id)

        db.session.commit()
    return usuario


def criar_categorias_padrao(usuario_id):
    """Cria categorias padrão para o usuário."""
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
    """Cria conta padrão 'Carteira' para o usuário."""
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
# BACKGROUND / AUTOMATIONS
# =============================================
cache_processamento = {}

@app.before_request
def processar_automaticos():
    # Evita processar em requisições de arquivos estáticos
    if request.path.startswith('/static/'):
        return

    usuario = get_user()
    if not usuario:
        return

    hoje = date.today()
    chave_cache = f"{usuario.id}_{hoje.isoformat()}"

    if chave_cache in cache_processamento:
        return

    houve_mudancas = False

    # Processar transações fixas
    transacoes_fixas = TransacaoFixa.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    for tf in transacoes_fixas:
        if hoje.day >= tf.dia_vencimento and not tf.pago_no_mes(hoje.year, hoje.month):
            nova_t = Transacao(
                tipo=tf.tipo,
                valor=tf.valor,
                descricao=f"Fixo: {tf.nome}",
                data=datetime.now(),
                usuario_id=usuario.id,
                categoria_id=tf.categoria_id,
                conta_id=tf.conta_id
            )
            db.session.add(nova_t)
            tf.marcar_pago(hoje.year, hoje.month)
            houve_mudancas = True

    # Processar Orçamentos: renovação mensal
    mes_atual = hoje.month
    ano_atual = hoje.year

    orc_atuais = Orcamento.query.filter_by(usuario_id=usuario.id, mes=mes_atual, ano=ano_atual).count()
    if orc_atuais == 0:
        mes_ant = mes_atual - 1
        ano_ant = ano_atual
        if mes_ant == 0:
            mes_ant = 12
            ano_ant -= 1

        orc_anteriores = Orcamento.query.filter_by(usuario_id=usuario.id, mes=mes_ant, ano=ano_ant).all()
        for o in orc_anteriores:
            novo_o = Orcamento(
                categoria_id=o.categoria_id,
                valor_limite=o.valor_limite,
                mes=mes_atual,
                ano=ano_atual,
                usuario_id=usuario.id
            )
            db.session.add(novo_o)
            houve_mudancas = True

    if houve_mudancas:
        db.session.commit()
    cache_processamento[chave_cache] = True


def invalidar_cache_automaticos(usuario_id):
    hoje = date.today()
    chave = f"{usuario_id}_{hoje.isoformat()}"
    cache_processamento.pop(chave, None)


# Injetar o usuário em todos os templates
@app.context_processor
def inject_user():
    return dict(usuario=get_user())


# =============================================
# AUTOMAÇÕES (roda a cada request)
# =============================================

_automaticos_cache = {}  # {data_str: True} — evita rodar múltiplas vezes no mesmo dia


def processar_automaticos(usuario):
    """Processa transações fixas vencidas e renova orçamentos automaticamente."""
    hoje = date.today()
    chave = f"{usuario.id}-{hoje.isoformat()}"
    if chave in _automaticos_cache:
        return
    _automaticos_cache[chave] = True

    # 1) Lançar transações fixas vencidas automaticamente
    fixas = TransacaoFixa.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    lancou = 0
    for fixa in fixas:
        if not fixa.pago_no_mes(hoje.year, hoje.month) and hoje.day >= fixa.dia_vencimento:
            # Criar transação automática
            transacao = Transacao(
                tipo=fixa.tipo,
                valor=fixa.valor,
                descricao=f'[Auto] {fixa.nome}',
                data=datetime(hoje.year, hoje.month, min(fixa.dia_vencimento, cal_module.monthrange(hoje.year, hoje.month)[1])),
                usuario_id=usuario.id,
                categoria_id=fixa.categoria_id,
                conta_id=fixa.conta_id
            )
            db.session.add(transacao)
            fixa.marcar_pago(hoje.year, hoje.month)
            lancou += 1

    # 2) Renovar orçamentos do mês anterior
    orc_atual = Orcamento.query.filter_by(
        usuario_id=usuario.id, mes=hoje.month, ano=hoje.year
    ).count()
    if orc_atual == 0:
        # Buscar mês anterior
        if hoje.month == 1:
            mes_ant, ano_ant = 12, hoje.year - 1
        else:
            mes_ant, ano_ant = hoje.month - 1, hoje.year
        orcs_anteriores = Orcamento.query.filter_by(
            usuario_id=usuario.id, mes=mes_ant, ano=ano_ant
        ).all()
        for orc in orcs_anteriores:
            novo = Orcamento(
                categoria_id=orc.categoria_id,
                valor_limite=orc.valor_limite,
                mes=hoje.month,
                ano=hoje.year,
                usuario_id=usuario.id
            )
            db.session.add(novo)

    if lancou > 0 or orc_atual == 0:
        db.session.commit()


@app.before_request
def auto_processar():
    """Roda automações em cada request (com cache diário)."""
    # Só processa em rotas de página, não em estáticos
    if request.endpoint and request.endpoint != 'static':
        try:
            usuario = Usuario.query.first()
            if usuario:
                processar_automaticos(usuario)
        except Exception:
            pass


# =============================================
# HELPERS: INSIGHTS FINANCEIROS
# =============================================

def calcular_resumo_semanal(usuario):
    """Calcula gastos da semana atual vs semana anterior."""
    hoje = date.today()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana_ant = inicio_semana - timedelta(days=1)
    inicio_semana_ant = fim_semana_ant - timedelta(days=6)

    gastos_semana = db.session.query(db.func.coalesce(db.func.sum(Transacao.valor), 0)).filter(
        Transacao.usuario_id == usuario.id,
        Transacao.tipo == 'despesa',
        Transacao.data >= datetime.combine(inicio_semana, datetime.min.time()),
        Transacao.data <= datetime.combine(hoje, datetime.max.time())
    ).scalar() or 0

    gastos_semana_ant = db.session.query(db.func.coalesce(db.func.sum(Transacao.valor), 0)).filter(
        Transacao.usuario_id == usuario.id,
        Transacao.tipo == 'despesa',
        Transacao.data >= datetime.combine(inicio_semana_ant, datetime.min.time()),
        Transacao.data <= datetime.combine(fim_semana_ant, datetime.max.time())
    ).scalar() or 0

    variacao = 0
    if gastos_semana_ant > 0:
        variacao = round(((gastos_semana - gastos_semana_ant) / gastos_semana_ant) * 100, 1)

    receitas_mes = db.session.query(db.func.coalesce(db.func.sum(Transacao.valor), 0)).filter(
        Transacao.usuario_id == usuario.id,
        Transacao.tipo == 'receita',
        db.extract('month', Transacao.data) == hoje.month,
        db.extract('year', Transacao.data) == hoje.year
    ).scalar() or 0

    despesas_mes = db.session.query(db.func.coalesce(db.func.sum(Transacao.valor), 0)).filter(
        Transacao.usuario_id == usuario.id,
        Transacao.tipo == 'despesa',
        db.extract('month', Transacao.data) == hoje.month,
        db.extract('year', Transacao.data) == hoje.year
    ).scalar() or 0

    return {
        'gastos_semana': float(gastos_semana),
        'gastos_semana_ant': float(gastos_semana_ant),
        'variacao': variacao,
        'receitas_mes': float(receitas_mes),
        'despesas_mes': float(despesas_mes),
        'economia_mes': float(receitas_mes) - float(despesas_mes)
    }


def calcular_previsao_saldo(usuario):
    """Projeta saldo para os próximos 3 meses baseado em transações fixas."""
    hoje = date.today()
    contas = Conta.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    saldo_atual = sum(c.saldo_atual for c in contas)

    fixas = TransacaoFixa.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    receitas_fixas = sum(f.valor for f in fixas if f.tipo == 'receita')
    despesas_fixas = sum(f.valor for f in fixas if f.tipo == 'despesa')
    saldo_mensal = receitas_fixas - despesas_fixas

    previsao = []
    saldo = saldo_atual
    for i in range(1, 4):
        mes = hoje.month + i
        ano = hoje.year
        if mes > 12:
            mes -= 12
            ano += 1
        saldo += saldo_mensal
        nome_mes = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][mes-1]
        previsao.append({
            'mes': f'{nome_mes}/{ano}',
            'saldo': round(saldo, 2),
            'receitas': receitas_fixas,
            'despesas': despesas_fixas
        })

    return {
        'saldo_atual': saldo_atual,
        'saldo_mensal': saldo_mensal,
        'previsao': previsao
    }


def calcular_score_financeiro(usuario):
    """Score de 0-100 baseado em critérios de saúde financeira."""
    hoje = date.today()
    score = 50  # Base

    # 1) Receita vs Despesa do mês (até +20)
    receitas = db.session.query(db.func.coalesce(db.func.sum(Transacao.valor), 0)).filter(
        Transacao.usuario_id == usuario.id, Transacao.tipo == 'receita',
        db.extract('month', Transacao.data) == hoje.month,
        db.extract('year', Transacao.data) == hoje.year
    ).scalar() or 0
    despesas = db.session.query(db.func.coalesce(db.func.sum(Transacao.valor), 0)).filter(
        Transacao.usuario_id == usuario.id, Transacao.tipo == 'despesa',
        db.extract('month', Transacao.data) == hoje.month,
        db.extract('year', Transacao.data) == hoje.year
    ).scalar() or 0

    if receitas > 0:
        taxa_poupanca = (receitas - despesas) / receitas
        if taxa_poupanca >= 0.3:
            score += 20
        elif taxa_poupanca >= 0.1:
            score += 10
        elif taxa_poupanca < 0:
            score -= 15

    # 2) Orçamentos respeitados (até +15)
    orcs = Orcamento.query.filter_by(usuario_id=usuario.id, mes=hoje.month, ano=hoje.year).all()
    if orcs:
        dentro = sum(1 for o in orcs if o.percentual <= 100)
        score += int((dentro / len(orcs)) * 15)

    # 3) Contas fixas em dia (até +15)
    fixas = TransacaoFixa.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    if fixas:
        pagas = sum(1 for f in fixas if f.pago_no_mes(hoje.year, hoje.month))
        vencidas = sum(1 for f in fixas if f.status_atual == 'atrasado')
        score += int((pagas / len(fixas)) * 10)
        score -= vencidas * 3

    score = max(0, min(100, score))

    # Classificação
    if score >= 80:
        label, cor = 'Excelente', '#00d68f'
    elif score >= 60:
        label, cor = 'Bom', '#45b7d1'
    elif score >= 40:
        label, cor = 'Regular', '#ffd93d'
    else:
        label, cor = 'Atenção', '#ff6b6b'

    return {'score': score, 'label': label, 'cor': cor}


def detectar_gastos_incomuns(usuario):
    """Detecta transações recentes significativamente acima da média da categoria."""
    hoje = date.today()
    alertas = []

    # Últimas 10 despesas
    recentes = Transacao.query.filter_by(
        usuario_id=usuario.id, tipo='despesa'
    ).order_by(Transacao.data.desc()).limit(10).all()

    for t in recentes:
        if not t.categoria_id:
            continue
        # Média dos últimos 3 meses nessa categoria
        tres_meses_atras = hoje - timedelta(days=90)
        media = db.session.query(db.func.avg(Transacao.valor)).filter(
            Transacao.usuario_id == usuario.id,
            Transacao.tipo == 'despesa',
            Transacao.categoria_id == t.categoria_id,
            Transacao.data >= datetime.combine(tres_meses_atras, datetime.min.time()),
            Transacao.id != t.id
        ).scalar()

        if media and t.valor > media * 2 and t.valor > 50:
            alertas.append({
                'descricao': t.descricao or t.categoria_nome,
                'valor': t.valor,
                'media': round(float(media), 2),
                'categoria': t.categoria_nome,
                'data': t.data.strftime('%d/%m')
            })

    return alertas[:5]


# =============================================
# ROTAS PRINCIPAIS
# =============================================

@app.route('/')
def home():
    return redirect(url_for('dashboard'))


# =============================================
# DASHBOARD
# =============================================

@app.route('/dashboard')
def dashboard():
    usuario = get_user()
    mes_filtro = request.args.get('mes', '')
    ano_filtro = request.args.get('ano', '')
    categoria_filtro = request.args.get('categoria', '')
    conta_filtro = request.args.get('conta', '')

    query = Transacao.query.filter_by(usuario_id=usuario.id)

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

    categorias = Categoria.query.filter_by(usuario_id=usuario.id).order_by(Categoria.nome).all()
    contas = Conta.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    tags = Tag.query.filter_by(usuario_id=usuario.id).order_by(Tag.nome).all()

    # Gráfico de pizza (despesas por categoria)
    categorias_grafico = {}
    for t in transacoes:
        if t.tipo == 'despesa':
            nome = t.categoria_nome
            categorias_grafico[nome] = categorias_grafico.get(nome, 0) + t.valor

    # Anos para filtro
    todas = Transacao.query.filter_by(usuario_id=usuario.id).all()
    anos = sorted(set(t.data.year for t in todas), reverse=True) or [datetime.now().year]

    # Orçamentos do mês atual
    hoje = date.today()
    orcamentos = Orcamento.query.filter_by(
        usuario_id=usuario.id,
        mes=hoje.month,
        ano=hoje.year
    ).all()

    # Despesas fixas pendentes
    transacoes_fixas = TransacaoFixa.query.filter_by(
        usuario_id=usuario.id,
        ativo=True
    ).all()
    pendentes = [d for d in transacoes_fixas if d.status_atual in ('pendente', 'proximo', 'atrasado')]

    # Saldo total de todas as contas
    saldo_total = sum(c.saldo_atual for c in contas)

    # Insights
    resumo = calcular_resumo_semanal(usuario)
    previsao = calcular_previsao_saldo(usuario)
    score = calcular_score_financeiro(usuario)
    alertas_gastos = detectar_gastos_incomuns(usuario)

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
                           pendentes=pendentes,
                           resumo=resumo,
                           previsao=previsao,
                           score=score,
                           alertas_gastos=alertas_gastos)


# =============================================
# TRANSAÇÕES CRUD
# =============================================

@app.route('/transacao/nova', methods=['POST'])
def nova_transacao():
    usuario = get_user()
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
        usuario_id=usuario.id,
        categoria_id=int(categoria_id) if categoria_id else None,
        conta_id=int(conta_id) if conta_id else None
    )

    # Adicionar tags
    if tag_ids:
        tags = Tag.query.filter(Tag.id.in_(tag_ids), Tag.usuario_id == usuario.id).all()
        transacao.tags = tags

    db.session.add(transacao)
    db.session.commit()
    flash(f'{"Receita" if tipo == "receita" else "Despesa"} adicionada!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transacao/editar/<int:id>', methods=['POST'])
def editar_transacao(id):
    usuario = get_user()
    transacao = Transacao.query.get_or_404(id)

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
        tags = Tag.query.filter(Tag.id.in_(tag_ids), Tag.usuario_id == usuario.id).all()
        transacao.tags = tags
    else:
        transacao.tags = []

    db.session.commit()
    flash('Transação atualizada!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transacao/excluir/<int:id>', methods=['POST'])
def excluir_transacao(id):
    transacao = Transacao.query.get_or_404(id)
    db.session.delete(transacao)
    db.session.commit()
    flash('Transação excluída!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transacao/duplicar/<int:id>', methods=['POST'])
def duplicar_transacao(id):
    original = Transacao.query.get_or_404(id)
    nova = Transacao(
        tipo=original.tipo,
        valor=original.valor,
        descricao=f'{original.descricao or ""} (cópia)',
        data=datetime.now(),
        usuario_id=original.usuario_id,
        categoria_id=original.categoria_id,
        conta_id=original.conta_id
    )
    db.session.add(nova)
    db.session.commit()
    flash('Transação duplicada!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transacao/parcelada', methods=['POST'])
def nova_transacao_parcelada():
    usuario = get_user()
    tipo = request.form.get('tipo', '').strip().lower()
    valor_total = request.form.get('valor', '')
    num_parcelas = request.form.get('parcelas', '')
    categoria_id = request.form.get('categoria_id', '')
    conta_id = request.form.get('conta_id', '')
    descricao = request.form.get('descricao', '').strip()
    data_str = request.form.get('data', '')

    if tipo not in ('receita', 'despesa'):
        flash('Tipo inválido.', 'error')
        return redirect(url_for('dashboard'))

    try:
        valor_total = float(valor_total)
        num_parcelas = int(num_parcelas)
        if valor_total <= 0 or num_parcelas < 2 or num_parcelas > 60:
            raise ValueError
    except (ValueError, TypeError):
        flash('Valores inválidos. Parcelas entre 2 e 60.', 'error')
        return redirect(url_for('dashboard'))

    data_inicio = datetime.now()
    if data_str:
        try:
            data_inicio = datetime.strptime(data_str, '%Y-%m-%d')
        except ValueError:
            pass

    valor_parcela = round(valor_total / num_parcelas, 2)
    grupo_id = str(uuid.uuid4())

    for i in range(num_parcelas):
        # Calcula data de cada parcela (mês a mês)
        mes = data_inicio.month + i
        ano = data_inicio.year
        while mes > 12:
            mes -= 12
            ano += 1
        dia = min(data_inicio.day, cal_module.monthrange(ano, mes)[1])
        data_parcela = datetime(ano, mes, dia)

        transacao = Transacao(
            tipo=tipo,
            valor=valor_parcela,
            descricao=f'{descricao} ({i+1}/{num_parcelas})',
            data=data_parcela,
            usuario_id=usuario.id,
            categoria_id=int(categoria_id) if categoria_id else None,
            conta_id=int(conta_id) if conta_id else None,
            parcela_grupo_id=grupo_id,
            parcela_num=i + 1,
            parcela_total=num_parcelas
        )
        db.session.add(transacao)

    db.session.commit()
    flash(f'{num_parcelas}x de R$ {valor_parcela:.2f} criadas!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transferir', methods=['POST'])
def transferir():
    usuario = get_user()
    conta_origem_id = request.form.get('conta_origem', '')
    conta_destino_id = request.form.get('conta_destino', '')
    valor = request.form.get('valor', '')
    descricao = request.form.get('descricao', '').strip() or 'Transferência entre contas'

    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError
        conta_origem_id = int(conta_origem_id)
        conta_destino_id = int(conta_destino_id)
        if conta_origem_id == conta_destino_id:
            flash('Contas devem ser diferentes.', 'error')
            return redirect(url_for('contas'))
    except (ValueError, TypeError):
        flash('Valores inválidos.', 'error')
        return redirect(url_for('contas'))

    conta_origem = Conta.query.get_or_404(conta_origem_id)
    conta_destino = Conta.query.get_or_404(conta_destino_id)

    # Despesa na conta origem
    saida = Transacao(
        tipo='despesa', valor=valor,
        descricao=f'↗ {descricao} → {conta_destino.nome}',
        data=datetime.now(), usuario_id=usuario.id,
        conta_id=conta_origem_id
    )
    # Receita na conta destino
    entrada = Transacao(
        tipo='receita', valor=valor,
        descricao=f'↙ {descricao} ← {conta_origem.nome}',
        data=datetime.now(), usuario_id=usuario.id,
        conta_id=conta_destino_id
    )
    db.session.add(saida)
    db.session.add(entrada)
    db.session.commit()
    flash(f'Transferência de R$ {valor:.2f} realizada!', 'success')
    return redirect(url_for('contas'))


@app.route('/importar', methods=['GET', 'POST'])
def importar():
    usuario = get_user()
    categorias = Categoria.query.filter_by(usuario_id=usuario.id).order_by(Categoria.nome).all()
    contas = Conta.query.filter_by(usuario_id=usuario.id, ativo=True).all()

    if request.method == 'POST':
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('importar'))

        file = request.files['arquivo']
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('importar'))

        categoria_id = request.form.get('categoria_id', '')
        conta_id = request.form.get('conta_id', '')

        try:
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content), delimiter=';')

            # Tenta detectar o delimitador
            if not reader.fieldnames or len(reader.fieldnames) <= 1:
                content = file.stream.read().decode('utf-8-sig') if hasattr(file.stream, 'read') else content
                reader = csv.DictReader(io.StringIO(content), delimiter=',')

            count = 0
            for row in reader:
                # Tenta pegar os campos com nomes comuns
                data_str = row.get('Data') or row.get('data') or row.get('DATE') or ''
                valor_str = row.get('Valor') or row.get('valor') or row.get('VALUE') or row.get('Amount') or ''
                desc = row.get('Descrição') or row.get('descricao') or row.get('Descricao') or row.get('DESCRIPTION') or row.get('Historico') or ''
                tipo_str = row.get('Tipo') or row.get('tipo') or row.get('TYPE') or ''

                if not valor_str:
                    continue

                # Limpa e converte valor
                valor_str = valor_str.strip().replace('R$', '').replace(' ', '')
                if ',' in valor_str and '.' in valor_str:
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                elif ',' in valor_str:
                    valor_str = valor_str.replace(',', '.')

                try:
                    valor = float(valor_str)
                except ValueError:
                    continue

                # Determina tipo
                if tipo_str.lower() in ('receita', 'credito', 'crédito', 'credit', 'c'):
                    tipo = 'receita'
                elif tipo_str.lower() in ('despesa', 'debito', 'débito', 'debit', 'd'):
                    tipo = 'despesa'
                elif valor < 0:
                    tipo = 'despesa'
                    valor = abs(valor)
                else:
                    tipo = 'receita'

                # Parse da data
                data = datetime.now()
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%y'):
                    try:
                        data = datetime.strptime(data_str.strip(), fmt)
                        break
                    except ValueError:
                        continue

                transacao = Transacao(
                    tipo=tipo, valor=valor,
                    descricao=desc.strip()[:200],
                    data=data, usuario_id=usuario.id,
                    categoria_id=int(categoria_id) if categoria_id else None,
                    conta_id=int(conta_id) if conta_id else None
                )
                db.session.add(transacao)
                count += 1

            db.session.commit()
            flash(f'{count} transações importadas com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao importar: {str(e)}', 'error')

        return redirect(url_for('importar'))

    return render_template('importar.html', categorias=categorias, contas=contas)


@app.route('/api/insights')
def api_insights():
    usuario = get_user()
    resumo = calcular_resumo_semanal(usuario)
    previsao = calcular_previsao_saldo(usuario)
    score = calcular_score_financeiro(usuario)
    alertas = detectar_gastos_incomuns(usuario)
    return jsonify({
        'resumo': resumo,
        'previsao': previsao,
        'score': score,
        'alertas': alertas
    })


# =============================================
# CONTAS CRUD
# =============================================

@app.route('/contas')
def contas():
    usuario = get_user()
    contas = Conta.query.filter_by(usuario_id=usuario.id).all()
    return render_template('contas.html', contas=contas)


@app.route('/conta/nova', methods=['POST'])
def nova_conta():
    usuario = get_user()
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
                  cor=cor, icone=icone, usuario_id=usuario.id)
    db.session.add(conta)
    db.session.commit()
    flash('Conta criada!', 'success')
    return redirect(url_for('contas'))


@app.route('/conta/editar/<int:id>', methods=['POST'])
def editar_conta(id):
    conta = Conta.query.get_or_404(id)

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
def excluir_conta(id):
    conta = Conta.query.get_or_404(id)
    db.session.delete(conta)
    db.session.commit()
    flash('Conta excluída!', 'success')
    return redirect(url_for('contas'))


# =============================================
# CATEGORIAS CRUD
# =============================================

@app.route('/categorias')
def categorias():
    usuario = get_user()
    cats = Categoria.query.filter_by(usuario_id=usuario.id).order_by(Categoria.tipo, Categoria.nome).all()
    return render_template('categorias.html', categorias=cats)


@app.route('/categoria/nova', methods=['POST'])
def nova_categoria():
    usuario = get_user()
    nome = request.form.get('nome', '').strip()
    tipo = request.form.get('tipo', 'despesa')
    icone = request.form.get('icone', 'fa-tag')
    cor = request.form.get('cor', '#7c5cfc')

    if not nome:
        flash('Informe o nome da categoria.', 'error')
        return redirect(url_for('categorias'))

    cat = Categoria(nome=nome, tipo=tipo, icone=icone, cor=cor, usuario_id=usuario.id)
    db.session.add(cat)
    db.session.commit()
    flash('Categoria criada!', 'success')
    return redirect(url_for('categorias'))


@app.route('/categoria/excluir/<int:id>', methods=['POST'])
def excluir_categoria(id):
    cat = Categoria.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('Categoria excluída!', 'success')
    return redirect(url_for('categorias'))


# =============================================
# TAGS CRUD
# =============================================

@app.route('/tag/nova', methods=['POST'])
def nova_tag():
    usuario = get_user()
    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#45b7d1')

    if not nome:
        flash('Informe o nome da tag.', 'error')
        return redirect(url_for('categorias'))

    tag = Tag(nome=nome, cor=cor, usuario_id=usuario.id)
    db.session.add(tag)
    db.session.commit()
    flash('Tag criada!', 'success')
    return redirect(url_for('categorias'))


@app.route('/tag/excluir/<int:id>', methods=['POST'])
def excluir_tag(id):
    tag = Tag.query.get_or_404(id)
    db.session.delete(tag)
    db.session.commit()
    flash('Tag excluída!', 'success')
    return redirect(url_for('categorias'))


# =============================================
# TRANSAÇÕES FIXAS
# =============================================

@app.route('/transacoes-fixas/<tipo>')
def transacoes_fixas(tipo):
    usuario = get_user()
    if tipo not in ('receita', 'despesa'):
        tipo = 'despesa'

    transacoes = TransacaoFixa.query.filter_by(usuario_id=usuario.id, tipo=tipo).order_by(TransacaoFixa.dia_vencimento).all()
    categorias = Categoria.query.filter_by(usuario_id=usuario.id, tipo=tipo).all()
    contas = Conta.query.filter_by(usuario_id=usuario.id, ativo=True).all()
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
def nova_transacao_fixa():
    usuario = get_user()
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
        usuario_id=usuario.id
    )
    db.session.add(transacao_fixa)
    db.session.commit()
    
    # Se a transação estiver atrasada e no mesmo mês, force o reprocessamento
    invalidar_cache_automaticos(usuario.id)
    
    flash('Transação fixa criada!', 'success')
    return redirect(target_url)


@app.route('/transacao-fixa/pagar/<int:id>', methods=['POST'])
def pagar_transacao_fixa(id):
    usuario = get_user()
    transacao_fixa = TransacaoFixa.query.get_or_404(id)

    target_url = url_for('transacoes_fixas', tipo=transacao_fixa.tipo)

    hoje = date.today()
    transacao_fixa.marcar_pago(hoje.year, hoje.month)

    # Cria transação automática
    transacao = Transacao(
        tipo=transacao_fixa.tipo,
        valor=transacao_fixa.valor,
        descricao=f'Fixo: {transacao_fixa.nome}',
        data=datetime.now(),
        usuario_id=usuario.id,
        categoria_id=transacao_fixa.categoria_id,
        conta_id=transacao_fixa.conta_id
    )
    db.session.add(transacao)
    db.session.commit()
    flash(f'{transacao_fixa.nome} contabilizada neste mês!', 'success')
    return redirect(target_url)


@app.route('/transacao-fixa/excluir/<int:id>', methods=['POST'])
def excluir_transacao_fixa(id):
    transacao_fixa = TransacaoFixa.query.get_or_404(id)
    tipo = transacao_fixa.tipo
    db.session.delete(transacao_fixa)
    db.session.commit()
    flash('Transação fixa excluída!', 'success')
    return redirect(url_for('transacoes_fixas', tipo=tipo))


# =============================================
# ORÇAMENTOS
# =============================================

@app.route('/orcamentos')
def orcamentos():
    usuario = get_user()
    hoje = date.today()
    mes = request.args.get('mes', hoje.month, type=int)
    ano = request.args.get('ano', hoje.year, type=int)

    orcs = Orcamento.query.filter_by(
        usuario_id=usuario.id, mes=mes, ano=ano
    ).all()
    categorias = Categoria.query.filter_by(usuario_id=usuario.id, tipo='despesa').all()

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
def novo_orcamento():
    usuario = get_user()
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
            usuario_id=usuario.id
        )
        db.session.add(orc)
        db.session.commit()
        invalidar_cache_automaticos(usuario.id)
        flash('Orçamento criado!', 'success')
    except (ValueError, TypeError):
        flash('Valores inválidos.', 'error')

    return redirect(url_for('orcamentos'))


@app.route('/orcamento/excluir/<int:id>', methods=['POST'])
def excluir_orcamento(id):
    orc = Orcamento.query.get_or_404(id)
    db.session.delete(orc)
    db.session.commit()
    flash('Orçamento excluído!', 'success')
    return redirect(url_for('orcamentos'))


# =============================================
# METAS FINANCEIRAS
# =============================================

@app.route('/metas')
def metas():
    usuario = get_user()
    metas_ativas = Meta.query.filter_by(usuario_id=usuario.id, concluida=False).order_by(Meta.prazo).all()
    metas_concluidas = Meta.query.filter_by(usuario_id=usuario.id, concluida=True).all()

    total_alvo = sum(m.valor_alvo for m in metas_ativas)
    total_acumulado = sum(m.valor_atual for m in metas_ativas)

    return render_template('metas.html',
                           metas_ativas=metas_ativas,
                           metas_concluidas=metas_concluidas,
                           total_alvo=total_alvo,
                           total_acumulado=total_acumulado)


@app.route('/meta/nova', methods=['POST'])
def nova_meta():
    usuario = get_user()
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
        prazo=prazo, icone=icone, cor=cor, usuario_id=usuario.id
    )
    db.session.add(meta)
    db.session.commit()
    flash('Meta criada!', 'success')
    return redirect(url_for('metas'))


@app.route('/meta/depositar/<int:id>', methods=['POST'])
def depositar_meta(id):
    meta = Meta.query.get_or_404(id)

    valor = request.form.get('valor', '')
    descricao = request.form.get('descricao', '').strip()
    try:
        valor = float(valor)
        if valor <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Valor inválido.', 'error')
        return redirect(url_for('metas'))

    # Registrar depósito no histórico
    deposito = DepositoMeta(
        meta_id=meta.id,
        valor=valor,
        descricao=descricao or f'Depósito de R$ {valor:.2f}'
    )
    db.session.add(deposito)

    meta.valor_atual = min(meta.valor_atual + valor, meta.valor_alvo)
    if meta.valor_atual >= meta.valor_alvo:
        meta.concluida = True
        flash(f'🎉 Meta "{meta.nome}" concluída!', 'success')
    else:
        flash(f'Depósito de R$ {valor:.2f} realizado!', 'success')

    db.session.commit()
    return redirect(url_for('metas'))


@app.route('/meta/excluir/<int:id>', methods=['POST'])
def excluir_meta(id):
    meta = Meta.query.get_or_404(id)
    db.session.delete(meta)
    db.session.commit()
    flash('Meta excluída!', 'success')
    return redirect(url_for('metas'))


# =============================================
# CARTÕES DE CRÉDITO
# =============================================

@app.route('/cartoes')
def cartoes():
    usuario = get_user()
    cards = CartaoCredito.query.filter_by(usuario_id=usuario.id).all()
    contas = Conta.query.filter_by(usuario_id=usuario.id, ativo=True).all()
    return render_template('cartoes.html', cartoes=cards, contas=contas)


@app.route('/cartao/novo', methods=['POST'])
def novo_cartao():
    usuario = get_user()
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
        usuario_id=usuario.id
    )
    db.session.add(conta_cartao)
    db.session.flush()

    cartao = CartaoCredito(
        nome=nome, bandeira=bandeira, limite=limite,
        dia_fechamento=dia_fechamento, dia_vencimento=dia_vencimento,
        cor=cor, conta_id=conta_cartao.id, usuario_id=usuario.id
    )
    db.session.add(cartao)
    db.session.commit()
    flash(f'Cartão {nome} cadastrado!', 'success')
    return redirect(url_for('cartoes'))


@app.route('/cartao/excluir/<int:id>', methods=['POST'])
def excluir_cartao(id):
    cartao = CartaoCredito.query.get_or_404(id)
    db.session.delete(cartao)
    db.session.commit()
    flash('Cartão excluído!', 'success')
    return redirect(url_for('cartoes'))


# =============================================
# RELATÓRIOS
# =============================================

@app.route('/relatorios')
def relatorios():
    usuario = get_user()
    hoje = date.today()
    ano = request.args.get('ano', hoje.year, type=int)

    # Dados mensais do ano selecionado
    meses_dados = []
    for m in range(1, 13):
        transacoes_mes = Transacao.query.filter_by(
            usuario_id=usuario.id
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
        usuario_id=usuario.id, tipo='despesa'
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
        usuario_id=usuario.id, tipo='receita'
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
    todas = Transacao.query.filter_by(usuario_id=usuario.id).all()
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
def calendario():
    usuario = get_user()
    hoje = date.today()
    mes = request.args.get('mes', hoje.month, type=int)
    ano = request.args.get('ano', hoje.year, type=int)

    # Dias do mês
    primeiro_dia_semana, dias_no_mes = cal_module.monthrange(ano, mes)

    # Transações do mês agrupadas por dia
    transacoes_mes = Transacao.query.filter_by(
        usuario_id=usuario.id
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
        dias[dia]['transacoes'].append({
            'id': t.id,
            'tipo': t.tipo,
            'valor': t.valor,
            'descricao': t.descricao or '',
            'categoria': t.categoria_nome,
            'conta': t.conta.nome if t.conta else '',
            'data': t.data.strftime('%d/%m/%Y') if t.data else '',
        })

    # Despesas fixas do mês
    transacoes_fixas = TransacaoFixa.query.filter_by(
        usuario_id=usuario.id, ativo=True
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
def busca():
    usuario = get_user()
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    valor_min = request.args.get('valor_min', '')
    valor_max = request.args.get('valor_max', '')

    resultados = []
    total = 0

    if q or tipo or data_inicio or data_fim or valor_min or valor_max:
        query = Transacao.query.filter_by(usuario_id=usuario.id)

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
def perfil():
    usuario = get_user()
    total_transacoes = Transacao.query.filter_by(usuario_id=usuario.id).count()
    total_receitas = sum(t.valor for t in Transacao.query.filter_by(usuario_id=usuario.id, tipo='receita').all())
    total_despesas = sum(t.valor for t in Transacao.query.filter_by(usuario_id=usuario.id, tipo='despesa').all())
    total_contas = Conta.query.filter_by(usuario_id=usuario.id).count()
    metas_concluidas = Meta.query.filter_by(usuario_id=usuario.id, concluida=True).count()

    return render_template('perfil.html',
                           total_transacoes=total_transacoes,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           total_contas=total_contas,
                           metas_concluidas=metas_concluidas)


@app.route('/perfil/editar', methods=['POST'])
def editar_perfil():
    usuario = get_user()
    nome = request.form.get('nome', '').strip()

    if not nome:
        flash('Nome é obrigatório.', 'error')
        return redirect(url_for('perfil'))

    usuario.nome = nome
    db.session.commit()
    flash('Perfil atualizado!', 'success')
    return redirect(url_for('perfil'))


# =============================================
# TEMA
# =============================================

@app.route('/tema/toggle', methods=['POST'])
def toggle_tema():
    usuario = get_user()
    usuario.tema = 'light' if usuario.tema == 'dark' else 'dark'
    db.session.commit()
    return jsonify({'tema': usuario.tema})


# =============================================
# EXPORTAR CSV
# =============================================

@app.route('/exportar/csv')
def exportar_csv():
    usuario = get_user()
    mes = request.args.get('mes', None, type=int)
    ano = request.args.get('ano', None, type=int)

    query = Transacao.query.filter_by(usuario_id=usuario.id)
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
            t.conta.nome if t.conta else '',
            t.descricao or ''
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    filename = f'transacoes_{ano or "todos"}'
    if mes:
        filename += f'_{mes:02d}'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}.csv'
    return response


@app.route('/exportar/powerbi')
def exportar_powerbi():
    usuario = get_user()
    
    # Busca todas as transações, sem filtro de mês/ano para o Power BI ter o histórico completo
    transacoes = Transacao.query.filter_by(usuario_id=usuario.id).order_by(Transacao.data.asc()).all()

    output = io.StringIO()
    # Usando ponto e vírgula como delimitador (padrão PT-BR no Excel/Power BI)
    writer = csv.writer(output, delimiter=';')
    
    # Cabeçalho rico para BI
    writer.writerow([
        'ID_Transacao', 'Data', 'Ano', 'Mes', 'Dia', 'Tipo', 
        'Valor', 'Categoria', 'Conta', 'Descricao', 'Tags'
    ])

    for t in transacoes:
        # Extrair dados para colunas separadas facilita a criação de dimensões de tempo no Power BI
        ano = t.data.year if t.data else ''
        mes = t.data.month if t.data else ''
        dia = t.data.day if t.data else ''
        data_formatada = t.data.strftime('%Y-%m-%d') if t.data else '' # Formato ISO é melhor para BI
        
        # Tags agrupadas
        tags = ', '.join([tag.nome for tag in t.tags]) if t.tags else ''
        
        # Valor com ponto como separador decimal para evitar confusão com delimitador CSV (;) em alguns locales
        # Power BI lê 1500.50 perfeitamente configurado como inglês na coluna, ou pode ser tratado facilmente.
        # Vamos manter formato pt-BR (vírgula decimal num arquivo de delimitador ponto e vírgula)
        valor_str = f'{t.valor:.2f}'.replace('.', ',')

        writer.writerow([
            t.id,
            data_formatada,
            ano,
            mes,
            dia,
            t.tipo.capitalize(),
            valor_str,
            t.categoria_nome,
            t.conta_nome,
            t.descricao or '',
            tags
        ])

    # utf-8-sig adiciona o BOM, vital para o Excel e Power BI no Windows reconhecerem acentos corretamente
    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = 'attachment; filename=dados_powerbi.csv'
    return response


# =============================================
# UPLOAD DE COMPROVANTES
# =============================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/transacao/comprovante/<int:id>', methods=['POST'])
def upload_comprovante(id):
    transacao = Transacao.query.get_or_404(id)

    if 'comprovante' not in request.files:
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('dashboard'))

    file = request.files['comprovante']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('dashboard'))

    if file and allowed_file(file.filename):
        try:
            # Enviar para o Cloudinary
            upload_result = cloudinary.uploader.upload(file, resource_type='auto')
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
