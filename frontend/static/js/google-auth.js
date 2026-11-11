/* GIS verifies the Google account; Flask verifies the credential and CSRF. */
window.flatlandGoogleSignIn = function (response) {
  const form = document.getElementById('google-signin-form');
  if (!form || !response.credential) return;
  form.elements.credential.value = response.credential;
  form.submit();
};

// Give Google's official button the same usable width as the form fields.
// clientWidth excludes the account card's entrance transform.
(function () {
  const host = document.querySelector('.authx__google .g_id_signin');
  if (!host) return;
  let width = Math.min(400, host.clientWidth);
  host.setAttribute('data-width', String(width));
  let resizeTimer;
  window.addEventListener('resize', function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(function () {
      const nextWidth = Math.min(400, host.clientWidth);
      if (nextWidth === width || nextWidth < 1) return;
      width = nextWidth;
      host.setAttribute('data-width', String(width));
      if (window.google && window.google.accounts && window.google.accounts.id) {
        window.google.accounts.id.renderButton(host, {
          type: 'standard', theme: 'outline', size: 'large',
          text: 'continue_with', shape: 'rectangular',
          logo_alignment: 'center', locale: 'en', width: String(width)
        });
      }
    }, 150);
  });
})();
