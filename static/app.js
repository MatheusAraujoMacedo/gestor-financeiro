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
