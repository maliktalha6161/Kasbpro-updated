function toggleView() {
    document.getElementById('request-view').classList.toggle('hidden');
    document.getElementById('success-view').classList.toggle('hidden');
}

document.getElementById('forgot-password-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    if (!email) return;
    document.getElementById('user-email').textContent = email;
    toggleView();
});
