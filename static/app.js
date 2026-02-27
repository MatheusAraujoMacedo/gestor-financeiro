// ==========================================
// FinançasPro - App JavaScript v2
// ==========================================

// --- Navbar scroll ---
const navbar = document.getElementById('navbar');
if (navbar) {
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 20);
    });
}

// --- Mobile menu ---
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');
if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
        navToggle.classList.toggle('active');
        navLinks.classList.toggle('active');
    });
    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            navToggle.classList.remove('active');
            navLinks.classList.remove('active');
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
