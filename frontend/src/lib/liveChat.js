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
 * The chat bubble shows on the applicant and agent dashboards
 * (`useLiveChatBubble`) and nowhere else. The Support page's own button opens
 * the same chat with `openLiveChat`.
 */

const PROPERTY_ID = (import.meta.env.VITE_TAWK_PROPERTY_ID || '6abe5477d9e778343f63237e').trim();
const WIDGET_ID = (import.meta.env.VITE_TAWK_WIDGET_ID || '1k3rnjt2u').trim();

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

/** Open the chat window. Resolves once it is open; rejects if it cannot load. */
export async function openLiveChat(visitor) {
  if (!isLiveChatConfigured()) throw new Error('Live chat is not set up yet.');
  const api = await load(visitor);
  api.showWidget?.();
  api.maximize?.();
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
