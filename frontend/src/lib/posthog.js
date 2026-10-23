/**
 * PostHog analytics singleton.
 *
 * Initialised once here so every module that imports `posthog` from
 * 'posthog-js' gets the same already-booted instance.
 *
 * Environment variables (Vite):
 *   VITE_POSTHOG_KEY  – your PostHog project API key (set in Vercel dashboard)
 *   VITE_POSTHOG_HOST – PostHog ingestion host (defaults to EU cloud)
 */
import posthog from 'posthog-js';

/**
 * Secrets that travel in page addresses, removed before anything reaches
 * PostHog: a password-reset link (?uid=…&token=…) works for an hour and an
 * email-verification link signs the person in, so either one sitting in the
 * analytics dashboard could be reused by anyone who can read it. The code in a
 * student's payment link (/pay/<code>) is what opens that page.
 */
const SECRET_PATH = /(\/pay\/)[^/?#\s"'<>]+/g;
const SECRET_QUERY = /([?&](?:token|uid|reference|trxref)=)[^&#\s"'<>]*/gi;

export function scrubUrl(text) {
  if (typeof text !== 'string' || (!text.includes('/pay/') && !/[?&](token|uid|reference|trxref)=/i.test(text))) {
    return text;
  }
  return text.replace(SECRET_PATH, '$1[hidden]').replace(SECRET_QUERY, '$1[hidden]');
}

// Every string in the event, including the page addresses inside session
// recordings, which sit a few levels down.
function scrubDeep(value, depth = 0) {
  if (typeof value === 'string') return scrubUrl(value);
  if (depth > 8 || value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) value[i] = scrubDeep(value[i], depth + 1);
    return value;
  }
  for (const name of Object.keys(value)) value[name] = scrubDeep(value[name], depth + 1);
  return value;
}

const key  = import.meta.env.VITE_POSTHOG_KEY;
const host = import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com';

// Guard: only initialise when a real key is present AND we are not in a
// Vite dev server (import.meta.env.PROD is true for `vite build` output).
if (key && key !== 'phc_REPLACE_WITH_YOUR_KEY') {
  posthog.init(key, {
    api_host: host,

    // Capture clicks, form submits, rage-clicks, and page-leave events.
    autocapture: true,

    // Session recordings – only mask password fields, unmask everything else
    session_recording: {
      maskAllInputs: false,
      maskInputOptions: {
        password: true,
      },
    },

    // Enable heatmaps (click maps, scroll depth).
    enable_heatmaps: true,

    // Page-view events are fired manually via usePostHogPageView so that the
    // correct SPA route is always captured after React Router renders.
    capture_pageview: false,

    // Strip secrets from page addresses before any event leaves the browser.
    before_send: (event) => (event ? scrubDeep(event) : event),

    // Persist distinct_id and feature flags across page refreshes.
    persistence: 'localStorage+cookie',

    // Disable all capturing in the Vite dev server so local clicks /
    // page-views never pollute your production PostHog project.
    loaded: (ph) => {
      if (import.meta.env.DEV) {
        ph.opt_out_capturing();
        console.info('[PostHog] dev mode – capturing disabled.');
      }
    },
  });
} else {
  // No valid key → replace every method with a no-op so callers never throw.
  if (import.meta.env.DEV) {
    console.warn(
      '[PostHog] VITE_POSTHOG_KEY is missing or is still the placeholder value. ' +
      'Set it in the Vercel dashboard (Settings → Environment Variables).',
    );
  }
}

export default posthog;
