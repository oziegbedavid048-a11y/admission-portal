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

const key  = import.meta.env.VITE_POSTHOG_KEY;
const host = import.meta.env.VITE_POSTHOG_HOST || 'https://eu.i.posthog.com';

// Guard: only initialise when a real key is present AND we are not in a
// Vite dev server (import.meta.env.PROD is true for `vite build` output).
if (key && key !== 'phc_REPLACE_WITH_YOUR_KEY') {
  posthog.init(key, {
    api_host: host,

    // Capture clicks, form submits, rage-clicks, and page-leave events.
    autocapture: true,

    // Session recordings – inputs are masked to protect personal data.
    session_recording: {
      maskAllInputs: true,
      maskTextSelector: '[data-ph-mask]', // add this attribute to any sensitive element
    },

    // Enable heatmaps (click maps, scroll depth).
    enable_heatmaps: true,

    // Page-view events are fired manually via usePostHogPageView so that the
    // correct SPA route is always captured after React Router renders.
    capture_pageview: false,

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
