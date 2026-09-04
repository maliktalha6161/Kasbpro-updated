/* Sign-up form logic */

const LOCAL_USERS_KEY = 'kasbpro_local_users';

function loadLocalUsers() {
    try { return JSON.parse(localStorage.getItem(LOCAL_USERS_KEY)) || []; }
    catch (e) { return []; }
}
function saveLocalUsers(arr) {
    localStorage.setItem(LOCAL_USERS_KEY, JSON.stringify(arr));
}

document.getElementById('signupForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const fullName        = document.getElementById('fullname').value.trim();
    const email           = document.getElementById('email').value.trim();
    const password        = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const terms           = document.getElementById('terms').checked;
    const roleEl          = document.querySelector('input[name="role"]:checked');

    /* Validation */
    if (!roleEl) {
        alert('Please choose a role — Admin, Owner, or Staff.');
        return;
    }
    if (!fullName || !email || !password) {
        alert('Please fill in all required fields.');
        return;
    }
    if (password.length < 6) {
        alert('Password must be at least 6 characters long.');
        return;
    }
    if (password !== confirmPassword) {
        alert('Passwords do not match.');
        return;
    }
    if (!terms) {
        alert('Please accept the Terms of Service to continue.');
        return;
    }

    const role = roleEl.value;            // 'admin', 'owner', or 'staff'
    const btn  = document.querySelector('.signup-btn');
    const orig = btn.innerText;
    btn.innerText = 'Creating Account...';
    btn.disabled = true;

    /* Try the back end first */
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: fullName, email, password, role })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                alert('Account created successfully! Please log in.');
                window.location.href = '2login.html';
                return;
            } else {
                throw new Error(data.message || 'Registration failed.');
            }
        } else {
            throw new Error('API not available');
        }
    } catch (apiErr) {
        /* Offline fallback */
        const users = loadLocalUsers();
        if (users.find(u => u.email.toLowerCase() === email.toLowerCase())) {
            alert('An account with that email already exists. Please log in instead.');
            btn.innerText = orig;
            btn.disabled = false;
            return;
        }
        users.push({ fullName, email, password, role });
        saveLocalUsers(users);
        alert('Account created (demo mode). Please log in.');
        window.location.href = '2login.html';
    } finally {
        btn.innerText = orig;
        btn.disabled = false;
    }
});
