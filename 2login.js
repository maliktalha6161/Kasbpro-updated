/* Login logic */

const LOCAL_USERS_KEY = 'kasbpro_local_users';

function loadLocalUsers() {
    try { return JSON.parse(localStorage.getItem(LOCAL_USERS_KEY)) || []; }
    catch (e) { return []; }
}

document.getElementById('loginForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const email    = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    if (!email || !password) {
        alert('Please enter both email and password.');
        return;
    }

    const btn  = document.querySelector('.login-btn');
    const orig = btn.innerText;
    btn.innerText = 'Logging in...';
    btn.disabled  = true;

    /* Try the back-end API first */
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success && data.user) {
                /* The API must return at least: full_name, email, role */
                kasbpro_setSession({
                    fullName: data.user.full_name || data.user.fullName || email,
                    email:    data.user.email     || email,
                    role:     (data.user.role || 'admin').toLowerCase()
                });
                window.location.href = 'dashboard.html';
                return;
            } else {
                throw new Error(data.message || 'Invalid credentials');
            }
        } else {
            throw new Error('API not available');
        }
    } catch (apiErr) {
        /* Fallback: locally registered users */
        const localUsers = loadLocalUsers();
        const localMatch = localUsers.find(u =>
            u.email.toLowerCase() === email.toLowerCase() && u.password === password);

        if (localMatch) {
            kasbpro_setSession({
                fullName: localMatch.fullName,
                email:    localMatch.email,
                role:     localMatch.role
            });
            window.location.href = 'dashboard.html';
            return;
        }

        /* Fallback: built-in demo accounts */
        const demoMatch = kasbpro_demoLogin(email, password);
        if (demoMatch) {
            kasbpro_setSession(demoMatch);
            window.location.href = 'dashboard.html';
            return;
        }

        alert('Invalid email or password. Please try again.\n\nTip: you can use the demo Admin/Owner accounts shown on the left.');
    } finally {
        btn.innerText = orig;
        btn.disabled  = false;
    }
});
