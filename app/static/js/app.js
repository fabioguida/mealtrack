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

  // Household-measure chips and portion-estimate chips fill a grams field.
  document.addEventListener('click', function (e) {
    var chip = e.target.closest('[data-grams]');
    if (!chip) return;
    var row = chip.closest('.riga');
    var input = row ? row.querySelector('input[name="grams"]') : null;
    if (!input) {
      // Estimate chips live outside the rows: fill the last row added.
      var rows = document.querySelectorAll('#righe .riga input[name="grams"]');
      input = rows.length ? rows[rows.length - 1] : null;
    }
    if (!input) return;
    input.value = chip.getAttribute('data-grams');
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });

  // Confirmation on destructive forms.
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  });
  // Confetti on a milestone: once per day per browser, not on every visit.
  function confettiOnce(root) {
    var c = (root || document).querySelector('.coriandoli[data-celebrate]');
    if (!c) return;
    var key = 'coriandoli:' + c.getAttribute('data-celebrate');
    try {
      if (window.sessionStorage.getItem(key)) c.classList.add('fatto');
      else window.sessionStorage.setItem(key, '1');
    } catch (e) { /* private mode: just show them */ }
  }
  confettiOnce(document);
  document.addEventListener('htmx:afterSwap', function (e) { confettiOnce(e.detail.target); });
})();
