// ==========================================
// FinançasPro - App JavaScript v2
// ==========================================

// --- Mobile Sidebar Toggle ---
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebarToggleClose = document.getElementById('sidebarToggleClose');

if (sidebar && sidebarToggle && sidebarToggleClose) {
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.add('open');
    });

    sidebarToggleClose.addEventListener('click', () => {
        sidebar.classList.remove('open');
    });

    // Close on click outside (mobile)
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });

    // Close when clicking links (mobile)
    sidebar.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
            }
        });
    });
}

// --- Flash auto-dismiss ---
const flashContainer = document.getElementById('flashContainer');
if (flashContainer) {
    flashContainer.querySelectorAll('.flash-message').forEach((msg, i) => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateX(40px)';
            setTimeout(() => msg.remove(), 300);
        }, 4000 + (i * 500));
    });
}

// --- Modal functions ---
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal(overlay.id);
    });
});

// Close on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => closeModal(m.id));
    }
});

// --- Edit transaction modal ---
function openEditModal(id, tipo, valor, categoriaId, contaId, descricao, data, tagIds) {
    const form = document.getElementById('editForm');
    if (!form) return;

    form.action = `/transacao/editar/${id}`;
    document.getElementById('edit-tipo').value = tipo;
    document.getElementById('edit-valor').value = valor;
    document.getElementById('edit-desc').value = descricao || '';
    document.getElementById('edit-data').value = data;

    const catSelect = document.getElementById('edit-cat');
    if (catSelect) catSelect.value = categoriaId || '';

    const contaSelect = document.getElementById('edit-conta');
    if (contaSelect) contaSelect.value = contaId || '';

    // Set tag checkboxes
    document.querySelectorAll('.edit-tag-checkbox').forEach(cb => {
        cb.checked = tagIds && tagIds.includes(parseInt(cb.value));
    });

    openModal('editModal');
}

// --- Keyboard shortcuts ---
document.addEventListener('keydown', (e) => {
    // Don't trigger when typing in inputs/selects
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
    // Don't trigger if a modal is open
    if (document.querySelector('.modal-overlay.active')) return;

    switch (e.key.toLowerCase()) {
        case 'n':
            e.preventDefault();
            if (document.getElementById('addModal')) openModal('addModal');
            break;
        case 't':
            e.preventDefault();
            if (document.getElementById('transferModal')) openModal('transferModal');
            else if (document.getElementById('transferContaModal')) openModal('transferContaModal');
            break;
        case 'i':
            e.preventDefault();
            window.location.href = '/importar';
            break;
        case '?':
            // Show keyboard help
            const toast = document.createElement('div');
            toast.className = 'flash-message flash-info';
            toast.style.position = 'fixed';
            toast.style.bottom = '24px';
            toast.style.right = '24px';
            toast.style.zIndex = '9999';
            toast.innerHTML = `
                <i class="fas fa-keyboard"></i>
                <span>Atalhos: <b>N</b> Nova transação · <b>T</b> Transferir · <b>I</b> Importar · <b>Esc</b> Fechar modal</span>
            `;
            document.body.appendChild(toast);
            setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4000);
            break;
    }
});

// ==========================================
// CHATBOT (Assistente Virtual)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    const chatbotToggleBtn = document.getElementById('chatbotToggleBtn');
    const chatbotWindow = document.getElementById('chatbotWindow');
    const chatbotClose = document.getElementById('chatbotClose');
    const chatbotMessages = document.getElementById('chatbotMessages');
    const chatbotInputArea = document.getElementById('chatbotInputArea');
    const chatbotSendBtn = document.getElementById('chatbotSendBtn');
    
    let hasLoadedNotifications = false;

    if (!chatbotToggleBtn) return;

    // Abrir/Fechar
    chatbotToggleBtn.addEventListener('click', () => {
        chatbotWindow.classList.toggle('active');
        if (chatbotWindow.classList.contains('active')) {
            chatbotInputArea.focus();
            if (!hasLoadedNotifications) {
                checkNotifications();
            }
        }
    });

    chatbotClose.addEventListener('click', () => {
        chatbotWindow.classList.remove('active');
    });

    // Histórico de conversa em memória (sessão do navegador)
    window.chatHistory = window.chatHistory || [];

    // Função de adicionar mensagem na tela
    function addMessage(text, sender, isError = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chatbot-msg ${sender} ${isError ? 'error' : ''}`;
        
        // Vamos renderizar markdown simples (bold) vindo do Gemini
        let formatText = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
        msgDiv.innerHTML = formatText;
        
        chatbotMessages.appendChild(msgDiv);
        
        // Scroll para baixo
        chatbotMessages.scrollTo({
            top: chatbotMessages.scrollHeight,
            behavior: 'smooth'
        });
        
        // Alimentar Mémoria Local se não for erro (para enviar na próxima call pro Gemini)
        if (!isError) {
            chatHistory.push({
                "role": sender === 'user' ? 'user' : 'model',
                "text": text
            });
            // Manter apenas as últimas 20 mensagens em contexto pra não bugar a API
            if (chatHistory.length > 20) chatHistory.shift();
        }
    }

    // Buscar Vencimentos Próximos
    async function checkNotifications() {
        hasLoadedNotifications = true;
        try {
            const res = await fetch('/api/bot/notificacoes');
            const data = await res.json();
            
            if (data.alertas && data.resposta) {
                setTimeout(() => {
                    addMessage(data.resposta, 'bot');
                }, 800);
            } else {
                // Mensagem de boas vindas inteligente
                setTimeout(() => {
                    addMessage("Olá! Sou a **Inteligência Artificial** do Gestor Pro. Como posso te ajudar hoje?", 'bot');
                }, 800);
            }
        } catch (e) {
            console.error("Erro ao carregar notificações do bot:", e);
        }
    }

    // Enviar mensagem pro servidor
    async function sendMessage() {
        const text = chatbotInputArea.value.trim();
        if (!text) return;
        
        // UI e Bloqueio de Input
        chatbotInputArea.disabled = true;
        chatbotInputArea.value = '';
        addMessage(text, 'user');
        
        const typingId = 'typing-' + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chatbot-msg bot';
        typingDiv.id = typingId;
        typingDiv.innerHTML = '<i class="fas fa-brain fa-fade"></i> <small style="opacity:0.7">Pensando...</small>';
        chatbotMessages.appendChild(typingDiv);
        chatbotMessages.scrollTo({ top: chatbotMessages.scrollHeight, behavior: 'smooth' });

        try {
            // Mandando a frase atual e a memória da conversa!
            const res = await fetch('/api/bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    mensagem: text,
                    history: window.chatHistory.slice(0, -1) // Manda tudo, menos a que o usuario acabou de mandar q ja foi empurrada no addMessage
                })
            });
            const data = await res.json();
            
            document.getElementById(typingId)?.remove();
            chatbotInputArea.disabled = false;
            chatbotInputArea.focus();
            
            if (data.status === 'success') {
                addMessage(data.resposta, 'bot');
            } else if (data.status === 'function_call') {
                 // Tratar calls diretos, mas nossa API Backend já executa a Tool lá e devolve a Resposta pronta!
                 // A API manda "success" e is_function_result
                 addMessage(data.resposta, 'bot');
            } else {
                addMessage(data.resposta || 'Erro desconhecido', 'bot', true);
            }
            
            // Relar o dashboard de fundo se o backend disser que efetuou uma Função que muda Banco de Dados
            if (data.is_function_result) {
                if (window.location.pathname === '/dashboard') {
                    setTimeout(() => window.location.reload(), 2500);
                }
            }
            
        } catch (e) {
            document.getElementById(typingId)?.remove();
            chatbotInputArea.disabled = false;
            addMessage("❌ Erro de conexão com a IA.", 'bot', true);
            console.error("Erro no bot AI:", e);
        }
    }

    chatbotSendBtn.addEventListener('click', sendMessage);
    chatbotInputArea.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !chatbotInputArea.disabled) sendMessage();
    });
});
