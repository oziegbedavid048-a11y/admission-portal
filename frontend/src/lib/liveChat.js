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
 * In the applicant and agent dashboards it is reached from the Support button
 * (components/ui/SupportLauncher.jsx): the widget is loaded in the background
 * but kept out of sight (`useLiveChat`), and opens only when someone picks
 * Live chat from the Support menu (`openLiveChat`). Closing it puts it away
 * again, so the Support button is the one way in.
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

// Bottom right, where the Support button is, so the chat opens beside it.
const POSITION = {
  visibility: {
    desktop: { position: 'br', xOffset: 24, yOffset: 24 },
    mobile: { position: 'br', xOffset: 12, yOffset: 12 },
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
 * Load the live chat in the background while the calling page is open, kept
 * out of sight until `openLiveChat` is called. Used by the applicant and agent
 * dashboards, which reach it from the Support button.
 */
export function useLiveChat(visitor) {
  const name = visitor?.name || '';
  const email = visitor?.email || '';

  useEffect(() => {
    if (!isLiveChatConfigured()) return undefined;
    bubbleWanted = false;
    load({ name, email })
      .then((api) => api.hideWidget?.())
      .catch(() => {});
    return () => {
      window.Tawk_API?.minimize?.();
      window.Tawk_API?.hideWidget?.();
    };
  }, [name, email]);
}

/** Open the chat window. Resolves false if the chat could not be loaded. */
export async function openLiveChat(visitor) {
  if (!isLiveChatConfigured()) return false;
  try {
    const api = await load(visitor);
    api.showWidget?.();
    api.maximize?.();
    return true;
  } catch {
    return false;
  }
}
