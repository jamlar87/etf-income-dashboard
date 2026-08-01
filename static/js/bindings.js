/* bindings.js — CSP-safe event delegation for the ETF income dashboard.
 *
 * Inline event handler attributes are blocked by the strict CSP, so
 * templates mark elements with data-click / data-change / data-input /
 * data-submit / data-onerror and this file delegates them to the named
 * global functions. Document-level delegation covers JS-rendered content.
 */
(function () {
  'use strict';

  function closest(el, selector) {
    return el && el.closest ? el.closest(selector) : null;
  }

  function dispatch(ev, attr, eventType) {
    var el = closest(ev.target, '[' + attr + ']');
    if (!el) return;
    var fnName = el.getAttribute(attr);
    if (!fnName) return;

    if (eventType === 'click') {
      if (fnName === 'markDirty') { if (window.markDirty) window.markDirty(el.dataset.ticker); return; }
      if (fnName === 'quickScore') { if (window.quickScore) window.quickScore(el.dataset.ticker, el.dataset.weight); return; }
      if (fnName === '__toggleNav') { var links = document.querySelector('.nav-links'); if (links) links.classList.toggle('open'); return; }
      if (fnName === '__reload') { window.location.reload(); return; }
    }
    if (eventType === 'change') {
      if (fnName === 'loadDate') { if (window.loadDate) window.loadDate(el.value); return; }
    }

    var fn = window[fnName];
    if (typeof fn === 'function') fn.call(el, ev);
  }

  document.addEventListener('click', function (ev) { dispatch(ev, 'data-click', 'click'); });
  document.addEventListener('change', function (ev) { dispatch(ev, 'data-change', 'change'); });
  document.addEventListener('input', function (ev) { dispatch(ev, 'data-input', 'input'); });
  document.addEventListener('submit', function (ev) { dispatch(ev, 'data-submit', 'submit'); });

  // error events don't bubble — capture phase
  document.addEventListener('error', function (ev) {
    var el = closest(ev.target, '[data-onerror]');
    if (el && el.getAttribute('data-onerror') === 'hide') el.style.display = 'none';
  }, true);
})();
