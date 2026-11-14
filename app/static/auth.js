/* ClerkJS handles session cookies; Flask verifies them independently on every protected request. */
window.addEventListener('load', async () => {
  const error = document.getElementById('auth-error');
  const form = document.getElementById('auth-form');
  const loading = document.getElementById('auth-loading');
  try {
    if (!window.Clerk || !window.__internal_ClerkUICtor) throw new Error('SDK unavailable');
    await window.Clerk.load({ui: {ClerkUI: window.__internal_ClerkUICtor}});
    const clerk = window.Clerk;
    const signedIn = clerk.isSignedIn;
    document.querySelectorAll('[data-signed-out]').forEach(element => {element.hidden = signedIn;});
    if (signedIn) {
      clerk.mountUserButton(document.getElementById('user-button'), {afterSignOutUrl: '/'});
      if (form) {
        // Make sure the short-lived same-origin session cookie is refreshed first.
        await clerk.session.getToken();
        window.location.replace(form.dataset.next || '/');
        return;
      }
    } else if (form) {
      const next = form.dataset.next || '/';
      const options = {
        routing: 'hash',
        signInUrl: '/sign-in?next=' + encodeURIComponent(next),
        signUpUrl: '/sign-up?next=' + encodeURIComponent(next),
        forceRedirectUrl: next,
        fallbackRedirectUrl: next,
      };
      if (form.dataset.mode === 'sign-up') clerk.mountSignUp(form, options);
      else clerk.mountSignIn(form, options);
    }
    if (loading) loading.hidden = true;
    clerk.addListener(({session}) => {
      document.querySelectorAll('[data-signed-out]').forEach(element => {element.hidden = Boolean(session);});
    });
  } catch (_) {
    if (loading) loading.hidden = true;
    if (error) error.hidden = false;
  }
});
