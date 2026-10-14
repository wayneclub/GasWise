/* GasWise Web: basic page measurement only; enhanced measurement is disabled. */
(() => {
  if (window.location.hostname !== 'gaswise.wayneclub.com' || window.gtag) return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
  });
  window.gtag('js', new Date());

  // URL queries and fragments can contain user input. Never send them to GA.
  let referrer = '';
  try {
    const url = new URL(document.referrer);
    referrer = url.origin + url.pathname;
  } catch { /* Direct visits have no referrer. */ }
  window.gtag('config', 'G-C9VZE31GQK', {
    page_location: window.location.origin + window.location.pathname,
    page_referrer: referrer,
    cookie_domain: 'gaswise.wayneclub.com',
    cookie_prefix: 'gaswise',
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
  });

  const tag = document.createElement('script');
  tag.async = true;
  tag.src = 'https://www.googletagmanager.com/gtag/js?id=G-C9VZE31GQK';
  document.head.appendChild(tag);
})();
