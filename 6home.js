document.addEventListener('DOMContentLoaded', () => {

    /* Mobile menu */
    const menuToggle = document.getElementById('mobile-menu');
    const navLinks   = document.querySelector('.nav-links');

    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            menuToggle.classList.toggle('is-active');
            navLinks.classList.toggle('active');
        });
        document.querySelectorAll('.nav-links a').forEach(link => {
            link.addEventListener('click', () => {
                menuToggle.classList.remove('is-active');
                navLinks.classList.remove('active');
            });
        });
    }

    /* Contact form demo */
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const btn = document.querySelector('.btn-send');
            const orig = btn.innerText;
            btn.innerText = 'Sending...';
            setTimeout(() => {
                alert('Thank you! Your message has been sent.');
                btn.innerText = orig;
                contactForm.reset();
            }, 800);
        });
    }
});
