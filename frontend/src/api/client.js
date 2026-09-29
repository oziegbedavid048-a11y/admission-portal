import axios from 'axios';

/**
 * Where the API is, worked out rather than trusted.
 *
 * `VITE_API_URL` is ambiguous by nature: "the backend" can reasonably mean
 * `https://host`, `https://host/api`, or just `/api`, and the two that are
 * missing the mount point produce a wall of 404s that look nothing like a
 * configuration mistake. That is exactly what happened in production: the
 * variable was set to the bare host, so every call went to `/auth/...` and
 * `/catalog/...` instead of `/api/auth/...` and `/api/catalog/...`, and the
 * backend answered 404 to all of it.
 *
 * Django mounts the API under `/api`, and the app knows that, so it appends it
 * when it is missing instead of depending on whoever set the variable. All of
 * these now resolve to the same place:
 *
 *   (unset)                             -> /api
 *   /api                                -> /api
 *   https://host                        -> https://host/api
 *   https://host/api/                   -> https://host/api
 */
function resolveApiBase(configured) {
  const trimmed = (configured || '').trim().replace(/\/+$/, '');
  if (!trimmed) return '/api';
  return /\/api$/i.test(trimmed) ? trimmed : `${trimmed}/api`;
}

const BASE_URL = resolveApiBase(import.meta.env.VITE_API_URL);

/**
 * The backend's own origin, for files it serves under /media/.
 *
 * An upload stored on the server comes back as a path such as
 * `/media/letters/...`. Resolved against the page, that path asked the website's
 * host for a file only the backend has, and every letter and document 404'd.
 * Paths are resolved against the API's origin instead. When the API is relative
 * (local development, or a same-origin proxy) this is empty and the page's own
 * origin is right.
 */
export const API_ORIGIN = /^https?:\/\//i.test(BASE_URL) ? new URL(BASE_URL).origin : '';

/**
 * The access token, held in memory only.
 *
 * Both tokens used to live in `localStorage`, which any script on the page can
 * read. One injected script — a compromised dependency, a reflected value — and
 * it walks off with a refresh token good for a week from anywhere.
 *
 * Now the refresh token is an httpOnly cookie the browser holds and no script can
 * see, and the access token lives here: a module variable, gone when the tab
 * closes, never written to disk. A session survives a reload because the app asks
 * the refresh endpoint for a new access token on boot, and the cookie is what
 * proves who is asking.
 *
 * The cookie requires the API and the site to be same-origin, which is why
 * BASE_URL defaults to a relative /api rather than a host.
 */
let accessToken = null;

export const tokenStore = {
  get access() {
    return accessToken;
  },
  save({ access }) {
    if (access) accessToken = access;
  },
  clear() {
    accessToken = null;
  },
};

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
  // Sends the refresh cookie on the one endpoint that needs it.
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

// One refresh at a time: if several calls expire together they all wait on the
// same request rather than each asking for a new token.
let refreshing = null;

/** Ask the cookie for a new access token. Resolves with the user, or throws. */
export async function restoreSession() {
  refreshing =
    refreshing ||
    axios.post(`${BASE_URL}/auth/refresh/`, {}, { withCredentials: true });
  try {
    const { data } = await refreshing;
    tokenStore.save(data);
    return data.user;
  } finally {
    refreshing = null;
  }
}

api.interceptors.response.use(
  (response) => {
    // If the server returned HTML when JSON was expected (e.g. Vercel SPA rewrite fallback for /api)
    const contentType = response.headers?.['content-type'] || '';
    if (typeof response.data === 'string' && (contentType.includes('text/html') || response.data.trim().startsWith('<!doctype') || response.data.trim().startsWith('<html'))) {
      const error = new Error('API returned HTML instead of JSON.');
      error.response = { ...response, status: 502, data: { detail: 'Cannot connect to backend API.' } };
      return Promise.reject(error);
    }
    return response;
  },
  async (error) => {
    const original = error.config;
    const status = error.response?.status;

    // The refresh endpoint failing is the end of the session, not something to
    // retry: retrying it would loop.
    const isRefresh = original?.url?.includes('/auth/refresh/');

    if (status === 401 && original && !original._retried && !isRefresh) {
      original._retried = true;
      try {
        await restoreSession();
        original.headers.Authorization = `Bearer ${accessToken}`;
        return api(original);
      } catch (refreshError) {
        tokenStore.clear();
        window.dispatchEvent(new CustomEvent('gabstep:signed-out'));
        return Promise.reject(refreshError);
      }
    }

    // A body that is not our JSON did not come from the API. It came from a CDN,
    // a proxy, or a load balancer answering in the API's place, and the message
    // inside it is about that hop rather than about what the person was doing.
    // Saying "could not create your account" for a misrouted request sends
    // somebody looking at the form when the request never arrived.
    const errData = error.response?.data;
    const errContentType = error.response?.headers?.['content-type'] || '';
    const bodyIsNotOurs =
      typeof errData === 'string' &&
      errData.trim() !== '' &&
      !errContentType.includes('application/json');
    if (
      bodyIsNotOurs ||
      (typeof errData === 'string' &&
        (errContentType.includes('text/html') ||
          errData.trim().startsWith('<!doctype') ||
          errData.trim().startsWith('<html') ||
          errData.trim().startsWith('<?xml') ||
          errData.includes('Traceback (most recent call last)')))
    ) {
      if (error.response) {
        // Name the status, because 404 here means the request went somewhere
        // that is not the API and that is a deployment fault, not a user one.
        error.response.data = {
          detail:
            error.response.status === 404
              ? 'The admissions server could not be reached at the configured address. This is a setup problem, not something you did.'
              : 'Unable to connect to the admissions server. Please try again in a moment.',
        };
      }
    }

    return Promise.reject(error);
  },
);

function stripHtml(input) {
  if (typeof input !== 'string') return '';
  return input.replace(/<[^>]*>?/gm, '').replace(/&nbsp;/g, ' ').trim();
}

function isHtmlOrCode(str) {
  if (typeof str !== 'string') return false;
  const lower = str.toLowerCase().trim();
  return (
    lower.startsWith('<!doctype') ||
    lower.startsWith('<html') ||
    lower.startsWith('<?xml') ||
    lower.includes('<body') ||
    lower.includes('<div') ||
    lower.includes('<title>') ||
    lower.includes('traceback (most recent call last)') ||
    lower.includes('django.core.exceptions')
  );
}

/** Turns a DRF error body into one sentence a person can act on. */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const data = error?.response?.data;
  if (error?.response?.status === 429) {
    return 'Too many attempts. Wait a minute and try again.';
  }
  if (!data) return error?.message === 'Network Error' ? 'Cannot reach the server.' : fallback;

  if (typeof data === 'string') {
    if (isHtmlOrCode(data)) return fallback;
    const clean = stripHtml(data);
    return clean && clean.length < 250 ? clean : fallback;
  }

  if (typeof data === 'object') {
    if (data.detail && typeof data.detail === 'string') {
      if (isHtmlOrCode(data.detail)) return fallback;
      const cleanDetail = stripHtml(data.detail);
      return cleanDetail || fallback;
    }

    const first = Object.entries(data)[0];
    if (!first) return fallback;
    const [field, value] = first;
    const text = Array.isArray(value) ? value[0] : value;
    if (typeof text === 'string') {
      if (isHtmlOrCode(text)) return fallback;
      const cleanText = stripHtml(text);
      if (field === 'non_field_errors') return cleanText || fallback;
      return cleanText || fallback;
    }
  }

  return fallback;
}

/** Field-level errors, keyed the way the forms key their inputs. */
export function fieldErrors(error) {
  const data = error?.response?.data;
  if (!data || typeof data !== 'object') return {};
  return Object.fromEntries(
    Object.entries(data)
      .filter(([key]) => key !== 'detail')
      .map(([key, value]) => [key, Array.isArray(value) ? value[0] : String(value)]),
  );
}

export default api;
