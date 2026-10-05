// Small behaviours. No inline scripts in templates (same rule as the Vere Novo site).
(function () {
  'use strict';

  // Phone menu.
  var nav = document.querySelector('nav');
  var menu = nav && nav.querySelector('.menu');
  if (menu) {
    menu.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      menu.setAttribute('aria-expanded', String(open));
    });
  }

  // Enter in the food search box must not submit the meal form.
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches('[data-food-search]')) e.preventDefault();
  });

  function recalc(form) {
    var rows = form && form.querySelector('#righe');
    if (rows) rows.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Remove an item row, then refresh the totals.
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-remove-row]');
    if (!btn) return;
    var form = btn.closest('form');
    btn.closest('.riga').remove();
    recalc(form);
  });

  // After a food is added: refresh totals, clear the search box and its results.
  document.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target.id !== 'righe') return;
    var form = e.detail.target.closest('form');
    recalc(form);
    var search = form.querySelector('[data-food-search]');
    if (search) search.value = '';
    var results = document.getElementById('risultati');
    if (results) results.innerHTML = '';
  });

  // Confirmation on destructive forms.
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  });
})();
