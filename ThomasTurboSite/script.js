/* script.js */
// Alternar tema claro/escuro
const toggleBtn = document.getElementById('theme-toggle');
const body = document.body;

function setTheme(isDark) {
    if (isDark) {
        body.classList.add('dark');
        toggleBtn.textContent = '☀️';
    } else {
        body.classList.remove('dark');
        toggleBtn.textContent = '🌙';
    }
    // Salvar preferência no localStorage
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Carregar tema salvo
const savedTheme = localStorage.getItem('theme');
setTheme(savedTheme === 'dark');

toggleBtn.addEventListener('click', () => {
    const isDark = body.classList.toggle('dark');
    setTheme(isDark);
});

// Simular envio de formulário (sem backend)
const form = document.getElementById('contato-form');
const feedback = document.getElementById('feedback');

form.addEventListener('submit', (e) => {
    e.preventDefault();
    // Coletar dados (apenas para demonstração)
    const nome = form.nome.value.trim();
    const email = form.email.value.trim();
    const mensagem = form.mensagem.value.trim();
    if (nome && email && mensagem) {
        feedback.textContent = `Obrigado, ${nome}! Recebemos sua mensagem.`;
        form.reset();
    } else {
        feedback.textContent = 'Por favor, preencha todos os campos obrigatórios.';
    }
});
