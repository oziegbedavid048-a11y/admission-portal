/**
 * usePostHogPageView
 *
 * Fires a `$pageview` event every time the React Router location changes.
 * Must be called inside a component that is already wrapped by <BrowserRouter>.
 *
 * Usage – call once near the top of App.jsx (or any component rendered for
 * every route):
 *
 *   import { usePostHogPageView } from '../hooks/usePostHogPageView';
 *   function App() {
 *     usePostHogPageView();
 *     …
 *   }
 */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import posthog from '../lib/posthog';

export function usePostHogPageView() {
  const location = useLocation();

  useEffect(() => {
    posthog.capture('$pageview', {
      $current_url: window.location.href,
    });
  }, [location.pathname, location.search]);
}
