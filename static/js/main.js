// Dark mode toggle
function initDarkMode() {
  const toggle = document.getElementById('dark-toggle');
  const html = document.documentElement;

  // Cargar preferencia guardada
  if (localStorage.theme === 'dark' ||
    (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    html.classList.add('dark');
  }

  if (toggle) {
    toggle.addEventListener('click', () => {
      html.classList.toggle('dark');
      localStorage.theme = html.classList.contains('dark') ? 'dark' : 'light';
    });
  }
}

// HTMX config
document.addEventListener('DOMContentLoaded', () => {
  initDarkMode();

  // CSRF token para HTMX y jQuery AJAX
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];

  // jQuery AJAX global setup
  if (typeof $ !== 'undefined') {
    $.ajaxSetup({
      headers: { 'X-CSRFToken': csrfToken }
    });
  }

  // HTMX CSRF
  document.body.addEventListener('htmx:configRequest', (e) => {
    e.detail.headers['X-CSRFToken'] = csrfToken;
  });
});