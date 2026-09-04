/* Shared authentication, roles, and UI helpers */

/* Role catalogue */
const KASBPRO_ROLES = Object.freeze({
    ADMIN: 'admin',
    OWNER: 'owner',
    STAFF: 'staff'
});

/* What each role is allowed to DO. Billing uses canCreate for invoices;
   record controls use explicit role markers where permissions differ. */
const KASBPRO_PERMISSIONS = Object.freeze({
    [KASBPRO_ROLES.ADMIN]: {
        canCreate: true,
        canEdit:   true,
        canDelete: false,
        canView:   true,
        label:     'Administrator'
    },
    [KASBPRO_ROLES.OWNER]: {
        canCreate: true,
        canEdit:   true,
        canDelete: true,
        canView:   true,
        label:     'Owner'
    },
    [KASBPRO_ROLES.STAFF]: {
        canCreate: true,
        canEdit:   false,
        canDelete: false,
        canView:   true,
        label:     'Staff'
    }
});

/* Session helpers
   We use sessionStorage so the session ends when the browser tab
   is closed — the right default for a business app. If you later
   add "Remember me" on the login page, swap to localStorage. */
const KASBPRO_SESSION_KEY = 'kasbpro_session';

function kasbpro_setSession(user) {
    /* user shape: { fullName, email, role } */
    sessionStorage.setItem(KASBPRO_SESSION_KEY, JSON.stringify(user));
}

function kasbpro_getSession() {
    try {
        const raw = sessionStorage.getItem(KASBPRO_SESSION_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        return null;
    }
}

function kasbpro_clearSession() {
    sessionStorage.removeItem(KASBPRO_SESSION_KEY);
}

function kasbpro_isLoggedIn() {
    const u = kasbpro_getSession();
    return !!(u && u.role);
}

function kasbpro_currentRole() {
    const u = kasbpro_getSession();
    return u ? u.role : null;
}

function kasbpro_can(action) {
    const role = kasbpro_currentRole();
    if (!role) return false;
    const perms = KASBPRO_PERMISSIONS[role];
    return !!(perms && perms[action]);
}

/* Route guard
   Call this at the very top of every protected page's inline
   <script> block, e.g.  kasbpro_requireAuth();
   It bounces unauthenticated visitors back to the login page. */
function kasbpro_requireAuth(loginUrl) {
    if (!kasbpro_isLoggedIn()) {
        window.location.replace(loginUrl || '2login.html');
        return false;
    }
    return true;
}

/* Legacy helper for any remaining Admin-only page. */
function kasbpro_requireAdmin() {
    if (!kasbpro_requireAuth()) return false;
    if (kasbpro_currentRole() !== KASBPRO_ROLES.ADMIN) {
        alert('This area is restricted to Administrators.');
        window.location.replace('dashboard.html');
        return false;
    }
    return true;
}

/* UI gating
   Mark any element in HTML with:
    data-role="admin,owner"     → Admins and Owners see it
    data-role="owner"           → only Owners see it
     data-perm="canCreate"       → hidden if role can't create
     data-perm="canEdit"         → hidden if role can't edit
     data-perm="canDelete"       → hidden if role can't delete
   Then call kasbpro_applyRoleUI() once on DOMContentLoaded. */
function kasbpro_applyRoleUI() {
    const role = kasbpro_currentRole();

    if (role === KASBPRO_ROLES.STAFF) {
        document.querySelectorAll('.nav-menu-upper .nav-item').forEach(item => {
            const link = item.querySelector('.nav-link');
            if (!link || !link.getAttribute('href').endsWith('billing.html')) {
                item.style.display = 'none';
            }
        });
    }

    document.querySelectorAll('[data-role]').forEach(el => {
        const allowed = el.getAttribute('data-role').split(',').map(s => s.trim());
        if (!allowed.includes(role)) el.style.display = 'none';
    });

    document.querySelectorAll('[data-perm]').forEach(el => {
        const perm = el.getAttribute('data-perm');
        if (!kasbpro_can(perm)) {
            /* For form controls, disable instead of hiding so layout stays intact */
            if (el.tagName === 'INPUT' || el.tagName === 'BUTTON' ||
                el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') {
                el.disabled = true;
                el.title = 'Read-only for this role';
            } else {
                el.style.display = 'none';
            }
        }
    });

    /* Auto-fill any element with class .js-user-name or .js-user-role */
    const session = kasbpro_getSession();
    if (session) {
        document.querySelectorAll('.js-user-name').forEach(el => {
            el.textContent = session.fullName || session.email || 'User';
        });
        document.querySelectorAll('.js-user-role').forEach(el => {
            el.textContent = KASBPRO_PERMISSIONS[session.role].label;
        });
        document.querySelectorAll('.js-user-initial').forEach(el => {
            const name = session.fullName || session.email || 'U';
            el.textContent = name.trim().charAt(0).toUpperCase();
        });
    }

}

/* Logout */
function logout() {
    /* hit the API too so the server-side session is dropped */
    fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })
        .catch(() => {})
        .finally(() => {
            kasbpro_clearSession();
            window.location.replace('2login.html');
        });
}

/* HTTP helper */
async function api(path, opts = {}) {
    const init = {
        method: opts.method || 'GET',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }
    };
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
    const r = await fetch(path, init);
    if (r.status === 401) {
        window.location.replace('2login.html');
        return null;
    }
    let data = null;
    try { data = await r.json(); } catch (e) { /* leave null */ }
    if (!r.ok) {
        const msg = (data && data.message) || ('HTTP ' + r.status);
        throw new Error(msg);
    }
    return data;
}

/* Toast notification */
function kasbpro_toast(message, kind = 'info') {
    const t = document.createElement('div');
    t.textContent = message;
    const palette = {
        info:  ['#2563eb', '#ffffff'],
        ok:    ['#10b981', '#ffffff'],
        err:   ['#dc2626', '#ffffff'],
        warn:  ['#f59e0b', '#1e293b']
    }[kind] || ['#2563eb', '#ffffff'];
    t.style.cssText =
        'position:fixed;top:24px;right:24px;max-width:340px;' +
        'background:' + palette[0] + ';color:' + palette[1] + ';' +
        'padding:12px 18px;border-radius:10px;font:600 14px/1.4 "Plus Jakarta Sans",sans-serif;' +
        'box-shadow:0 10px 25px rgba(0,0,0,.2);z-index:10001;opacity:0;' +
        'transform:translateY(-8px);transition:.25s;';
    document.body.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = '1'; t.style.transform = 'translateY(0)'; });
    setTimeout(() => {
        t.style.opacity = '0'; t.style.transform = 'translateY(-8px)';
        setTimeout(() => t.remove(), 250);
    }, 2800);
}

/* Modal helper
   Usage:
     kasbpro_modal({
        title: 'Add Product',
        fields: [
            { name:'name',     label:'Name',     type:'text',     required:true },
            { name:'price',    label:'Price (Rs)',type:'number',   required:true, step:'0.01' },
            { name:'stock',    label:'Stock',    type:'number',   required:true },
            { name:'category', label:'Category', type:'select', options:['General','Dairy',…] }
        ],
        initial: { ... }   // pre-fill for edit
     }).then(values => { ... });   // null if user cancelled
*/
function kasbpro_modal(opts) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.style.cssText =
            'position:fixed;inset:0;background:rgba(15,23,42,.55);' +
            'display:flex;align-items:center;justify-content:center;' +
            'z-index:10000;padding:20px;';

        const fields = (opts.fields || []).map(f => {
            const v = (opts.initial && opts.initial[f.name] != null) ? opts.initial[f.name] : '';
            if (f.type === 'select') {
                const optsHtml = (f.options || [])
                    .map(o => `<option value="${o}" ${o===v?'selected':''}>${o}</option>`).join('');
                return `<div style="margin-bottom:14px;">
                    <label style="display:block;font-size:.88rem;font-weight:600;color:#475569;margin-bottom:6px;">${f.label}</label>
                    <select name="${f.name}" style="width:100%;padding:11px 14px;border:1px solid #e2e8f0;border-radius:10px;outline:none;font-size:.95rem;">
                        ${optsHtml}
                    </select>
                </div>`;
            }
            if (f.type === 'textarea') {
                return `<div style="margin-bottom:14px;">
                    <label style="display:block;font-size:.88rem;font-weight:600;color:#475569;margin-bottom:6px;">${f.label}</label>
                    <textarea name="${f.name}" rows="3" style="width:100%;padding:11px 14px;border:1px solid #e2e8f0;border-radius:10px;outline:none;font-size:.95rem;resize:vertical;font-family:inherit;">${v}</textarea>
                </div>`;
            }
            const extra = (f.step ? `step="${f.step}"` : '') + (f.required ? ' required' : '') +
                          (f.min!=null ? ` min="${f.min}"` : '');
            return `<div style="margin-bottom:14px;">
                <label style="display:block;font-size:.88rem;font-weight:600;color:#475569;margin-bottom:6px;">${f.label}${f.required ? ' *' : ''}</label>
                <input name="${f.name}" type="${f.type||'text'}" value="${v}" ${extra}
                       style="width:100%;padding:11px 14px;border:1px solid #e2e8f0;border-radius:10px;outline:none;font-size:.95rem;">
            </div>`;
        }).join('');

        overlay.innerHTML = `
            <div style="background:white;border-radius:18px;width:100%;max-width:460px;
                        box-shadow:0 25px 60px rgba(0,0,0,.25);overflow:hidden;
                        font-family:'Plus Jakarta Sans',sans-serif;">
                <div style="padding:20px 26px;border-bottom:1px solid #eef2ff;display:flex;justify-content:space-between;align-items:center;">
                    <h3 style="margin:0;color:#1e3a8a;font-weight:800;font-size:1.1rem;">${opts.title || 'Form'}</h3>
                    <button type="button" data-kp="cancel"
                        style="background:none;border:none;font-size:1.4rem;color:#94a3b8;cursor:pointer;line-height:1;">×</button>
                </div>
                <form data-kp="form" style="padding:22px 26px;">
                    ${fields}
                    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:8px;">
                        <button type="button" data-kp="cancel"
                            style="background:#f1f5f9;color:#475569;border:none;padding:11px 20px;border-radius:10px;font-weight:700;cursor:pointer;font-size:.92rem;">
                            Cancel
                        </button>
                        <button type="submit"
                            style="background:#2563eb;color:white;border:none;padding:11px 20px;border-radius:10px;font-weight:700;cursor:pointer;font-size:.92rem;">
                            ${opts.submit || 'Save'}
                        </button>
                    </div>
                </form>
            </div>`;
        document.body.appendChild(overlay);

        const close = (value) => { overlay.remove(); resolve(value); };
        overlay.querySelectorAll('[data-kp="cancel"]').forEach(b => b.addEventListener('click', () => close(null)));
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(null); });
        overlay.querySelector('form').addEventListener('submit', (e) => {
            e.preventDefault();
            const fd = new FormData(e.target);
            const out = {};
            for (const [k, v] of fd.entries()) out[k] = v;
            close(out);
        });
        // focus first input
        setTimeout(() => overlay.querySelector('input,select,textarea')?.focus(), 50);
    });
}

/* Confirm dialog */
function kasbpro_confirm(message) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.style.cssText =
            'position:fixed;inset:0;background:rgba(15,23,42,.55);display:flex;' +
            'align-items:center;justify-content:center;z-index:10000;padding:20px;';
        overlay.innerHTML = `
            <div style="background:white;border-radius:18px;max-width:420px;width:100%;padding:28px;text-align:center;
                        font-family:'Plus Jakarta Sans',sans-serif;box-shadow:0 25px 60px rgba(0,0,0,.25);">
                <div style="width:56px;height:56px;border-radius:50%;background:#fee2e2;color:#dc2626;
                            display:flex;align-items:center;justify-content:center;font-size:1.6rem;
                            margin:0 auto 16px;">⚠</div>
                <p style="color:#1e293b;font-size:1rem;margin-bottom:24px;line-height:1.5;">${message}</p>
                <div style="display:flex;gap:10px;justify-content:center;">
                    <button data-kp="cancel"
                        style="background:#f1f5f9;color:#475569;border:none;padding:11px 22px;border-radius:10px;font-weight:700;cursor:pointer;">Cancel</button>
                    <button data-kp="ok"
                        style="background:#dc2626;color:white;border:none;padding:11px 22px;border-radius:10px;font-weight:700;cursor:pointer;">Delete</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
        const close = (v) => { overlay.remove(); resolve(v); };
        overlay.querySelector('[data-kp="cancel"]').addEventListener('click', () => close(false));
        overlay.querySelector('[data-kp="ok"]').addEventListener('click', () => close(true));
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
    });
}

/* Printable receipt
   Fetches an invoice and prints a clean, thermal-style receipt via a
   hidden iframe (no popup window, so it is never blocked by the browser).
   Usage:  kasbpro_printReceipt(invoiceId)
   Works for any invoice — point-of-sale or a reprint from history. */
const KASBPRO_STORE = Object.freeze({
    name:    'KasbPro Store',
    tagline: 'Smart Business Management',
    footer:  'Thank you for your purchase!'
});

async function kasbpro_printReceipt(invoiceId) {
    let d;
    try {
        d = await api('/api/invoices/' + invoiceId);
    } catch (e) {
        kasbpro_toast('Could not load invoice: ' + e.message, 'err');
        return;
    }
    if (!d || !d.invoice) { kasbpro_toast('Invoice not found', 'err'); return; }

    const inv = d.invoice, items = d.items || [];
    const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
    const money = (n) => 'Rs ' + (Number(n) || 0).toFixed(2);
    const when = inv.created_at
        ? new Date(inv.created_at.replace(' ', 'T')).toLocaleString('en-US',
            { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' })
        : '—';

    const rows = items.map(it => `
        <tr>
            <td class="it">${esc(it.product_name)}<br><span class="q">${it.quantity} × ${money(it.unit_price)}</span></td>
            <td class="amt">${money(it.line_total)}</td>
        </tr>`).join('');

    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(inv.invoice_number)}</title>
        <style>
            * { margin:0; padding:0; box-sizing:border-box; }
            body { font-family:'Courier New', monospace; color:#000; padding:10px; }
            .receipt { width:280px; margin:0 auto; }
            .center { text-align:center; }
            h1 { font-size:16px; letter-spacing:1px; }
            .muted { color:#444; font-size:11px; }
            .line { border-top:1px dashed #000; margin:8px 0; }
            .meta { font-size:11px; line-height:1.6; }
            table { width:100%; border-collapse:collapse; font-size:11px; }
            td { padding:4px 0; vertical-align:top; }
            td.amt { text-align:right; white-space:nowrap; }
            .q { color:#555; font-size:10px; }
            .total { display:flex; justify-content:space-between; font-weight:bold; font-size:14px; margin-top:6px; }
            .foot { text-align:center; font-size:11px; margin-top:10px; }
            @media print { body { padding:0; } }
        </style></head><body>
        <div class="receipt">
            <div class="center">
                <h1>${esc(KASBPRO_STORE.name)}</h1>
                <div class="muted">${esc(KASBPRO_STORE.tagline)}</div>
            </div>
            <div class="line"></div>
            <div class="meta">
                <strong>Invoice:</strong> ${esc(inv.invoice_number)}<br>
                <strong>Date:</strong> ${esc(when)}<br>
                <strong>Customer:</strong> ${esc(inv.customer_name || 'Walk-in')}<br>
                <strong>Status:</strong> ${esc(inv.status)}
            </div>
            <div class="line"></div>
            <table>${rows}</table>
            <div class="line"></div>
            ${Number(inv.tax) > 0 ? `<div class="meta"><span>Subtotal</span> ${money(inv.subtotal)}<br><span>Tax</span> ${money(inv.tax)}</div>` : ''}
            <div class="total"><span>TOTAL</span><span>${money(inv.total)}</span></div>
            <div class="line"></div>
            <div class="foot">${esc(KASBPRO_STORE.footer)}</div>
        </div>
    </body></html>`;

    const frame = document.createElement('iframe');
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;';
    document.body.appendChild(frame);
    const doc = frame.contentWindow.document;
    doc.open(); doc.write(html); doc.close();
    frame.contentWindow.focus();
    setTimeout(() => {
        try { frame.contentWindow.print(); } catch (e) { /* ignore */ }
        setTimeout(() => frame.remove(), 1500);
    }, 350);
}

/* Boot: hydrate session from /api/auth/me
   When a page loads, we ask the server who we are. If the back-end
   says we're logged in, we mirror that into sessionStorage so the
   existing role-aware UI keeps working. If the back-end says we're
   anonymous, we wipe local state. */
async function kasbpro_hydrateSession() {
    try {
        const r = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (r.ok) {
            const d = await r.json();
            if (d && d.success && d.user) {
                kasbpro_setSession({
                    fullName: d.user.full_name,
                    email:    d.user.email,
                    role:     d.user.role
                });
                return true;
            }
        }
    } catch (e) { /* offline mode */ }
    return false;
}

/* Demo accounts for offline fallback when the API is unavailable */
const KASBPRO_DEMO_USERS = [
    { fullName: 'Farhan Asif',    email: 'admin@kasbpro.com', password: 'admin123', role: KASBPRO_ROLES.ADMIN },
    { fullName: 'Muhammad Saad',  email: 'owner@kasbpro.com', password: 'owner123', role: KASBPRO_ROLES.OWNER }
];

function kasbpro_demoLogin(email, password) {
    const u = KASBPRO_DEMO_USERS.find(x =>
        x.email.toLowerCase() === String(email).toLowerCase() && x.password === password);
    if (!u) return null;
    return { fullName: u.fullName, email: u.email, role: u.role };
}
