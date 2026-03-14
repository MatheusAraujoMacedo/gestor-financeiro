# Gestor Financeiro 💸📊

Um **gestor financeiro pessoal** feito para ajudar você a ter clareza do seu dinheiro: registrar entradas e saídas, organizar por contas/categorias e acompanhar metas, orçamentos e despesas recorrentes.

> ⚠️ **Versão atual:** aplicação local (roda na sua máquina). Futuramente será disponibilizado na Play Store com login e pagamento.

---

## 🎯 Objetivo

Esse projeto nasceu com a ideia de transformar o "vou me organizar" em algo prático: **um painel simples e visual** para acompanhar finanças do dia a dia, sem depender de planilhas.

---

## ✅ Principais funcionalidades

- **Assistente Pro (IA via Google Gemini):** Converse naturalmente, cadastre gastos e consulte saldos direto pelo chat.
- **Dashboard** com visão geral das finanças (saldo, receitas, despesas)
- **Transações** (receitas e despesas) com descrição, data, categoria e conta
- **Contas** (carteira, conta corrente, poupança, investimento etc.)
- **Categorias** personalizáveis (receita/despesa)
- **Tags** para detalhar e filtrar transações
- **Receitas e despesas fixas (recorrentes)** com controle mensal e status
- **Orçamentos** por categoria e por mês
- **Metas financeiras** com progresso e prazo
- **Cartões de crédito** com limite, fatura e limite disponível
- **Calendário financeiro** para visualizar transações por dia
- **Relatórios** com gráficos anuais e top categorias
- **Busca avançada** com filtros (tipo, data, valor)
- **Exportação CSV** das transações
- **Comprovantes** — anexar arquivos em transações (via Cloudinary)
- **Tema escuro/claro** com alternância

---

## 🧱 Tecnologias

- **Python 3 + Flask**
- **Google Generative AI (Gemini API)** (Cérebro do assistente)
- **Flask-SQLAlchemy** (ORM)
- **SQLite** (banco de dados local)
- **HTML / CSS / JavaScript** (templates e front)
- **Cloudinary** (armazenamento de comprovantes)

---

## 🗂️ Estrutura do repositório

- `app.py` — aplicação Flask (rotas, regras de negócio e modelos)
- `templates/` — páginas HTML (views)
- `static/` — arquivos estáticos (CSS/JS/imagens)
- `requirements.txt` — dependências do projeto

---

## 🚀 Como executar na sua máquina

### Pré-requisitos

- **Python 3.10+** instalado ([Download aqui](https://www.python.org/downloads/))
- **Git** instalado ([Download aqui](https://git-scm.com/downloads))

### Passo a passo

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/MatheusAraujoMacedo/gestor-financeiro.git
   cd gestor-financeiro
   ```

2. **Crie e ative um ambiente virtual:**

   **Windows (CMD ou PowerShell):**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   **Linux / Mac:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuração das Variáveis de Ambiente:**
   Renomeie ou crie um arquivo `.env` na raiz do projeto com a seguinte variável obrigatória:
   ```env
   GEMINI_API_KEY=sua_chave_do_google_aqui
   ```
   *(Você pode pegar uma chave gratuita no [Google AI Studio](https://aistudio.google.com/app/apikey))*

5. **Execute a aplicação:**
   ```bash
   python app.py
   ```

5. **Acesse no navegador:**

   Abra: **http://127.0.0.1:5000**

   O app abrirá direto no **Dashboard** — não precisa criar conta nem fazer login!

### 💡 Dicas

- Na primeira execução, o banco de dados e um usuário padrão são **criados automaticamente**
- Seus dados ficam salvos no arquivo `instance/gestor.db` (SQLite local)
- Para parar o servidor, pressione `Ctrl+C` no terminal
- Para rodar novamente, basta repetir os passos 4 e 5 (ativar venv + `python app.py`)

---

## 🧭 Roadmap (próximas etapas)

- 📱 Publicar na **Play Store** como app mobile
- 🔐 Adicionar **sistema de login** e contas de usuário
- 💳 Implementar **planos e pagamentos**
- 📊 Relatórios mais completos (por período, por conta)
- 🔔 Notificações (despesa fixa próxima, orçamento estourando)

---

## 🤝 Contribuição

Sugestões e PRs são bem-vindos!
- Abra uma issue com feedback, bugs ou melhorias
- Envie um pull request com alterações objetivas e bem descritas

---

## 👤 Autor

**Matheus Araujo Macedo**  
GitHub: https://github.com/MatheusAraujoMacedo
