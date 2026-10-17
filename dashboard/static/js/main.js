/**
 * AEGIS ULTIMATE ESPORTS BOT — Dashboard JavaScript
 * Handles mobile sidebar toggle and small UI helpers.
 */

(function () {
    "use strict";

    // Mobile sidebar toggle
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("sidebar");

    if (menuToggle && sidebar) {
        menuToggle.addEventListener("click", function () {
            sidebar.classList.toggle("open");
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener("click", function (e) {
            if (
                window.innerWidth <= 768 &&
                sidebar.classList.contains("open") &&
                !sidebar.contains(e.target) &&
                e.target !== menuToggle
            ) {
                sidebar.classList.remove("open");
            }
        });
    }

    // Auto-dismiss flash messages after 6 seconds
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach(function (el) {
        setTimeout(function () {
            el.style.transition = "opacity 0.4s";
            el.style.opacity = "0";
            setTimeout(function () {
                el.remove();
            }, 400);
        }, 6000);
    });

    // Confirm dangerous form actions
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            const msg = form.getAttribute("data-confirm") || "Are you sure?";
            if (!window.confirm(msg)) {
                e.preventDefault();
            }
        });
    });
})();
