import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

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

    return Promise.reject(error);
  },
);

/** Turns a DRF error body into one sentence a person can act on. */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const data = error?.response?.data;
  if (error?.response?.status === 429) {
    return 'Too many attempts. Wait a minute and try again.';
  }
  if (!data) return error?.message === 'Network Error' ? 'Cannot reach the server.' : fallback;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;

  const first = Object.entries(data)[0];
  if (!first) return fallback;
  const [field, value] = first;
  const text = Array.isArray(value) ? value[0] : value;
  if (field === 'non_field_errors') return String(text);
  return typeof text === 'string' ? text : fallback;
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
