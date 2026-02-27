# Gestor Financeiro 💸📊

Um **gestor financeiro pessoal** feito para ajudar você a ter clareza do seu dinheiro: registrar entradas e saídas, organizar por contas/categorias e acompanhar metas, orçamentos e despesas recorrentes.

🔗 **Demo (deploy):** https://gestor-financeiro-fohb.onrender.com/

---

## 🎯 Objetivo

Esse projeto nasceu com a ideia de transformar o “vou me organizar” em algo prático: **um painel simples e visual** para acompanhar finanças do dia a dia, sem depender de planilhas.

---

## ✅ Principais funcionalidades

- **Cadastro e login de usuários**
- **Dashboard** com visão geral das finanças
- **Transações** (receitas e despesas) com descrição e data
- **Contas** (ex.: carteira, conta corrente, poupança, investimento etc.) e cálculo de saldo
- **Categorias** (receita/despesa) para organizar e analisar melhor
- **Tags** para detalhar e filtrar transações
- **Despesas fixas (recorrentes)** com controle mensal e status (pendente/próximo/atrasado/pago)
- **Orçamentos por categoria e por mês** (acompanhando gasto vs limite)
- **Metas** (ex.: juntar dinheiro) com progresso e prazo
- **Cartões de crédito** com limite, fatura do mês e limite disponível
- **Comprovantes**: possibilidade de anexar arquivo em transações (quando disponível na interface)
- **Tema** (ex.: dark/light) por usuário

> Obs.: As funcionalidades acima refletem o que está modelado e preparado no backend do projeto.

---

## 🧱 Tecnologias

- **Python + Flask**
- **Flask-Login** (autenticação)
- **Flask-SQLAlchemy** (ORM)
- **SQLite / Postgres** (dependendo do ambiente)
- **HTML / CSS / JavaScript** (templates e front)

---

## 🗂️ Estrutura do repositório

- `app.py` — aplicação Flask (rotas, regras de negócio e modelos)
- `templates/` — páginas HTML (views)
- `static/` — arquivos estáticos (CSS/JS/imagens)
- `requirements.txt` — dependências do projeto
- `render.yaml` — configuração de deploy (Render)

---

## 🧭 Roadmap (ideias futuras)

- Relatórios mais completos (por período, por conta, por categoria)
- Exportação/importação de dados (ex.: CSV) com UX melhor
- Melhorias no dashboard (gráficos e comparativos)
- Notificações/alertas (despesa fixa próxima do vencimento, orçamento estourando)

---

## 🤝 Contribuição

Sugestões e PRs são bem-vindos!
- Abra uma issue com feedback, bugs ou melhorias
- Envie um pull request com alterações objetivas e bem descritas

---

## 👤 Autor

**Matheus Araujo Macedo**  
GitHub: https://github.com/MatheusAraujoMacedo
