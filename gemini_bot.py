import os
import json
import traceback
from datetime import datetime
import google.generativeai as genai

# Configuração da Chave
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Definindo o Contexto de Personalidade e Regras (System Instruction)
SYSTEM_INSTRUCTION = """
Você é o "Assistente Pro", uma poderosa inteligência artificial financeira embutida num aplicativo chamado Gestor Financeiro.
Seu papel principal é ajudar o usuário a lançar gastos (despesas) e recebimentos (receitas) da forma mais natural possível, além de ser proativo e educado.

REGRAS:
1. Sempre seja conciso, direto e amigável.
2. Não use formatações complexas demais como tabelas enormes, pois a interface do chat é estreita.
3. SEMPRE que o usuário disser que comprou algo, gastou, recebeu ou transferiu, você DEVE INVOCAR A FUNÇÃO APROPRIADA Mapeada. Nunca diga que "você anotou" sem realmente chamar a ferramenta registrar_transacao.
4. O usuário não precisa informar o ano ao lançar transações. Assuma sempre o ano atual. O mês atual ou dias relativos (ontem, hoje) também devem ser deduzidos por você.
5. Se uma conta ou categoria mencionada não estiver nas listas conhecidas do usuário (contexto que te será passado), escolha a opção mais coerente disponível ou deixe como 'Outros' se existir.

Você tem permissão para ser proativo dando dicas financeiras curtas se o usuário gastar muito.
"""

# ==============================================================================
# DECLARAÇÃO DE FERRAMENTAS (FUNCTIONS) PARA O MODELO
# ==============================================================================
# Estas funções são as chaves de acesso que a IA terá para executar código real.

def registrar_transacao_tool(tipo: str, valor: float, descricao: str, conta_id: int, categoria_id: int, data_iso: str = None):
    """
    Registra uma nova transação financeira (despesa ou receita) no banco de dados do aplicativo.
    Use essa ferramenta SOMENTE se o usuário deixou CLARO que deseja incluir, adicionar, subtrair ou gastou/recebeu um dinheiro.
    
    Args:
        tipo: Deve ser obrigatoriamente "despesa" ou "receita".
        valor: O valor numérico e absoluto da transação (ex: 50.00). Nunca negativo.
        descricao: Resumo curto sobre do que se trata a transação.
        conta_id: O ID da conta (pego pelo contexto mapeado que foi lhe passado). Se desconhecida, procure a mais óbvia (ex: dinheiro, carteira) ou use a primeira.
        categoria_id: O ID da categoria (pego pelo contexto). Escolha a mais adequada (ex: Alimentação, Lazer).
        data_iso: (Opcional) A data no formato "YYYY-MM-DD". Se vázio, usará hoje.
    """
    pass # A implementação real não importa pro Gemini, apenas a assinatura (Typing) e as Docstrings


def consultar_saldo_tool(conta_id: int = None):
    """
    Lista o saldo atual do usuário.
    Se conta_id não for fornecido, retorna o Saldo Total.
    Se conta_id for fornecido, retorna apenas o valor daquela conta específica.
    """
    pass

# Agrupamos as ferramentas em uma lista
MINHAS_FERRAMENTAS = [registrar_transacao_tool, consultar_saldo_tool]


def call_gemini_bot(user_message, conversation_history, user_context_data):
    """
    Função principal que o Flask vai chamar para conversar com o Gemini.
    
    :param user_message: A última mensagem enviada pelo usuário.
    :param conversation_history: Uma lista de dicionários no formato Gemini com o histórico local.
    :param user_context_data: Um dicionário com as Contas, Categorias e Saldo atual do usuário.
    :return: A resposta em texto da IA e novas interações para adicionar no histórico.
    """
    
    # Criamos o contexto adicional que acompanha toda mensagem pro bot entender o panorama
    panorama_context = f"""
    [DADOS DO USUÁRIO NESTE MOMENTO]
    - Data e Hora Atual: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    - Saldo Total: R$ {user_context_data.get('saldo_total', 0):.2f}
    - Contas Ativas: {json.dumps(user_context_data.get('contas', []))}
    - Categorias de Despesa: {json.dumps(user_context_data.get('categorias_despesa', []))}
    - Categorias de Receita: {json.dumps(user_context_data.get('categorias_receita', []))}
    """

    try:
        # Instanciando o modelo
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_INSTRUCTION + panorama_context,
            tools=MINHAS_FERRAMENTAS
        )

        # Prepara a sessão de chat recriando o histórico que veio do front
        formatted_history = []
        for msg in conversation_history:
            formatted_history.append({
                "role": msg["role"], 
                "parts": [{"text": msg["text"]}]
            })
            
        chat_session = model.start_chat(history=formatted_history)

        # Envia a mensagem do usuario
        response = chat_session.send_message(user_message)

        # Trata se a IA decidiu chamar alguma função
        if response.parts and response.parts[0].function_call:
            fc = response.parts[0].function_call
            nome_funcao = fc.name
            args = {}
            for key, val in fc.args.items():
                args[key] = val
                
            return {
                "status": "function_call",
                "function_name": nome_funcao,
                "function_args": args,
                "role": "model",
                "parts": [{"function_call": {"name": nome_funcao, "args": args}}]
            }
        
        return {
            "status": "success",
            "resposta": response.text,
            "role": "model",
            "parts": [{"text": response.text}]
        }

    except Exception as e:
        print(f"Erro na IA: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "resposta": "Hmm, meus circuitos deram um pequeno tilt agora. Você pode repetir?",
            "detalhes": str(e)
        }
