/**
 * Live chat, behind one small interface so the provider can change without
 * touching the pages that offer it.
 *
 * It is Tawk.to today. Set these in the frontend environment to switch it on:
 *
 *   VITE_TAWK_PROPERTY_ID=<property id>
 *   VITE_TAWK_WIDGET_ID=<widget id, often "default">
 *
 * Both come from the Tawk.to dashboard under Administration › Chat widget. When
 * they are not set, `isLiveChatConfigured()` is false and the Support page says
 * live chat is not available, rather than offering a button that does nothing.
 *
 * The provider's floating bubble is kept hidden; the chat opens from the
 * Support page's own button, so the portals keep one consistent look.
 */

const PROPERTY_ID = (import.meta.env.VITE_TAWK_PROPERTY_ID || '').trim();
const WIDGET_ID = (import.meta.env.VITE_TAWK_WIDGET_ID || 'default').trim();

let loading = null;

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
      window.Tawk_API.hideWidget?.();
      resolve(window.Tawk_API);
    };
    // Closing the chat puts the bubble away again, rather than leaving it
    // floating over every page.
    window.Tawk_API.onChatMinimized = () => window.Tawk_API.hideWidget?.();

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
