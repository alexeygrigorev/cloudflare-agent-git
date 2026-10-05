/* Public Relay double opt-in. No subscriber data is kept in this browser. */
(function () {
  'use strict';
  var form = document.getElementById('journal-signup');
  if (!form) return;
  var input = document.getElementById('signup-email');
  var consent = document.getElementById('signup-consent');
  var button = document.getElementById('signup-submit');
  var status = document.getElementById('signup-status');
  if (!input || !consent || !button || !status) return;
  var label = button.textContent;
  var pending = false;
  var relay = form.dataset.relayList;
  var enabled = form.dataset.enabled !== 'false' &&
    relay === 'https://relay.datatalks.club/api/public/lists/agent-git-lab';
  var url = new URL(window.location.href);
  var confirmationPage = /\/subscribe\/?$/.test(url.pathname);
  var hasToken = confirmationPage && url.searchParams.has('token');
  var token = hasToken ? url.searchParams.get('token') : null;
  // Strip the secret before the first await, retaining unrelated query/hash data.
  if (hasToken) {
    url.searchParams.delete('token');
    window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
  }

  function show(message, kind) {
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle('is-error', kind === 'error');
    status.classList.toggle('is-ok', kind === 'ok');
  }

  function setPending(value, confirming) {
    pending = value;
    button.disabled = value;
    input.disabled = value;
    consent.disabled = value;
    form.setAttribute('aria-busy', value ? 'true' : 'false');
    button.textContent = value ? (confirming ? 'Confirming…' : 'Sending…') : label;
  }

  async function post(path, body) {
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 15000);
    try {
      var response = await fetch(relay + path, {
        method: 'POST',
        credentials: 'omit',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal
      });
      var payload = {};
      try { payload = await response.json(); } catch (_) { /* Fail closed below. */ }
      return { code: response.status, status: payload && payload.status };
    } finally {
      clearTimeout(timeout);
    }
  }

  function serviceError(result, confirming) {
    if (result.code === 429) return 'Too many requests. Please wait and try again later.';
    if (confirming && (result.code === 400 || result.code === 404 || result.code === 410)) {
      return 'That confirmation link is invalid or expired. Enter your email below to request a new link.';
    }
    if (!confirming && result.code === 400) return 'Enter a valid email address and try again.';
    return confirming ?
      'Could not confirm your email. Enter your email below to request a new link.' :
      'Could not send the confirmation link. Please try again later.';
  }

  function connectionError(error, confirming) {
    if (error && error.name === 'AbortError') return 'The request timed out. Please try again.';
    return confirming ?
      'Could not reach the confirmation service. Enter your email below to request a new link.' :
      'Could not reach the signup service. Check your connection and try again.';
  }

  async function confirm() {
    if (!token) {
      show('That confirmation link is invalid or expired. Enter your email below to request a new link.', 'error');
      return;
    }
    setPending(true, true);
    show('Confirming your email…', '');
    try {
      var result = await post('/confirm', { token: token });
      if (result.code === 200 && result.status === 'subscribed') {
        show('Your email is confirmed. You’re on the Agent Branches list.', 'ok');
      } else {
        show(serviceError(result, true), 'error');
      }
    } catch (error) {
      show(connectionError(error, true), 'error');
    } finally {
      token = null;
      setPending(false, false);
    }
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (pending) return;
    if (!enabled) {
      show('Email signup is not available yet. Please check back later.', 'error');
      return;
    }
    input.value = input.value.trim();
    if (!input.value || !input.checkValidity()) {
      show('Enter a valid email address.', 'error');
      input.reportValidity();
      return;
    }
    if (!consent.checked) {
      show('Please agree to receive the Agent Branches updates before signing up.', 'error');
      consent.reportValidity();
      return;
    }
    setPending(true, false);
    show('Requesting a confirmation link…', '');
    try {
      var result = await post('/subscribe', { email: input.value });
      if (result.code === 200 && result.status === 'verification_requested') {
        show('Check your inbox for a confirmation link. You’ll join the list after confirming.', 'ok');
        input.value = '';
        consent.checked = false;
      } else if (result.code === 200 && result.status === 'already_subscribed') {
        show('That email is already on the Agent Branches list.', 'ok');
        input.value = '';
        consent.checked = false;
      } else {
        show(serviceError(result, false), 'error');
      }
    } catch (error) {
      show(connectionError(error, false), 'error');
    } finally {
      setPending(false, false);
    }
  });

  if (hasToken) {
    if (enabled) void confirm();
    else show('Email confirmation is not available yet. Please request a new link when signup reopens.', 'error');
  }
})();
