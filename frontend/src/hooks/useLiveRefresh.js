import { useEffect, useRef } from 'react';

/**
 * Keep a page in step with changes made elsewhere — in practice, the admissions
 * desk approving something in the Django admin.
 *
 * It polls on an interval, and additionally refetches the moment the tab is
 * brought back to the front, which is when a stale screen is most likely to be
 * looked at. Polling rather than a socket is a deliberate trade: the data here
 * changes a few times a day, and a websocket stack would be a lot of moving
 * parts for a delay nobody would notice.
 *
 * It skips a tick while the tab is hidden, so a portal left open overnight is
 * not still calling the API in the morning.
 */
export default function useLiveRefresh(callback, { intervalMs = 20000, enabled = true } = {}) {
  const saved = useRef(callback);

  useEffect(() => {
    saved.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) return undefined;

    const run = () => {
      if (document.visibilityState === 'visible') saved.current?.();
    };

    const timer = window.setInterval(run, intervalMs);
    const onVisible = () => {
      if (document.visibilityState === 'visible') saved.current?.();
    };

    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [intervalMs, enabled]);
}
