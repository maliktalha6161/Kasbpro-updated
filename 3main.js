/* Homepage interactions */

document.addEventListener('DOMContentLoaded', () => {

    /* Mobile menu */
    const mobileToggle = document.getElementById('mobile-toggle');
    const navList      = document.getElementById('nav-list');

    if (mobileToggle && navList) {
        mobileToggle.addEventListener('click', () => {
            navList.classList.toggle('active');
        });

        /* Close menu after a link is tapped on mobile */
        navList.querySelectorAll('a').forEach(a => {
            a.addEventListener('click', () => navList.classList.remove('active'));
        });
    }

    /* Smooth scrolling */
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', e => {
            const id = anchor.getAttribute('href');
            if (id.length > 1) {
                const target = document.querySelector(id);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

});
