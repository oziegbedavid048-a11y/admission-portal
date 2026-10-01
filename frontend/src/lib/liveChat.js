import { useEffect } from 'react';

/**
 * Live chat, behind one small interface so the provider can change without
 * touching the pages that offer it.
 *
 * It is Tawk.to. The property and widget are Gabstep's own, from the Tawk.to
 * dashboard under Administration › Chat widget. They are public (they sit in
 * every page that shows the widget), and the environment can point at a
 * different widget:
 *
 *   VITE_TAWK_PROPERTY_ID=<property id>
 *   VITE_TAWK_WIDGET_ID=<widget id>
 *
 * The chat bubble shows at the bottom left of the applicant and agent
 * dashboards (`useLiveChatBubble`) and nowhere else.
 */

const DEFAULT_PROPERTY_ID = '6abe5477d9e778343f63237e';
const DEFAULT_WIDGET_ID = '1k3rnjt2u';

// A value from the environment is used only if it has the right shape. A
// property ID mistyped in the hosting settings (one character short) once
// stopped the chat loading for everyone; a malformed one now falls back to
// Gabstep's own widget instead.
function pick(value, pattern, fallback) {
  const clean = (value || '').trim();
  return pattern.test(clean) ? clean : fallback;
}

const PROPERTY_ID = pick(import.meta.env.VITE_TAWK_PROPERTY_ID, /^[a-f0-9]{24}$/i, DEFAULT_PROPERTY_ID);
const WIDGET_ID = pick(import.meta.env.VITE_TAWK_WIDGET_ID, /^[a-z0-9]{6,20}$/i, DEFAULT_WIDGET_ID);

// Bottom left on every screen size, clear of the page's own controls.
const POSITION = {
  visibility: {
    desktop: { position: 'bl', xOffset: 24, yOffset: 24 },
    mobile: { position: 'bl', xOffset: 12, yOffset: 12 },
    bubble: { rotate: '0deg', xOffset: 0, yOffset: 0 },
  },
};

let loading = null;
// Whether a page that wants the bubble is open. Read when the widget finishes
// loading and when the chat window is closed.
let bubbleWanted = false;

export function isLiveChatConfigured() {
  return Boolean(PROPERTY_ID);
}

function load(visitor) {
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    window.Tawk_API = window.Tawk_API || {};
    window.Tawk_LoadStart = new Date();
    window.Tawk_API.customStyle = POSITION;
    if (visitor?.name || visitor?.email) {
      window.Tawk_API.visitor = { name: visitor.name || '', email: visitor.email || '' };
    }
    window.Tawk_API.onLoad = () => {
      if (bubbleWanted) window.Tawk_API.showWidget?.();
      else window.Tawk_API.hideWidget?.();
      resolve(window.Tawk_API);
    };
    // Closing the chat leaves the bubble on the dashboards and puts it away
    // everywhere else.
    window.Tawk_API.onChatMinimized = () => {
      if (!bubbleWanted) window.Tawk_API.hideWidget?.();
    };

    const script = document.createElement('script');
    script.async = true;
    script.src = `https://embed.tawk.to/${encodeURIComponent(PROPERTY_ID)}/${encodeURIComponent(WIDGET_ID)}`;
    script.charset = 'UTF-8';
    script.setAttribute('crossorigin', '*');
    script.onerror = () => {
      loading = null;
      reject(new Error('Live chat could not be loaded.'));
    };
    document.body.appendChild(script);
  });
  return loading;
}

/**
 * Show the chat bubble while the calling page is open, and put it away when
 * it closes. Used by the applicant and agent dashboards.
 */
export function useLiveChatBubble(visitor) {
  const name = visitor?.name || '';
  const email = visitor?.email || '';

  useEffect(() => {
    if (!isLiveChatConfigured()) return undefined;
    bubbleWanted = true;
    load({ name, email })
      .then((api) => {
        if (bubbleWanted) api.showWidget?.();
      })
      .catch(() => {});
    return () => {
      bubbleWanted = false;
      window.Tawk_API?.minimize?.();
      window.Tawk_API?.hideWidget?.();
    };
  }, [name, email]);
}
