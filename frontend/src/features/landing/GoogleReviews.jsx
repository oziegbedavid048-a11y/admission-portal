import { useEffect, useRef } from 'react';

/**
 * Google reviews on the home page, through a Trustindex widget.
 *
 * Trustindex reads the business's Google reviews and keeps them up to date, so
 * the site needs no Google Cloud account. Set the widget's ID in the frontend
 * environment to switch it on:
 *
 *   VITE_TRUSTINDEX_WIDGET_ID=<id>
 *
 * The ID is the part after "?" in the embed code Trustindex gives you:
 * <script src="https://cdn.trustindex.io/loader.js?THIS_PART">. The whole URL
 * is accepted too. When it is not set the section is left out entirely rather
 * than showing an empty frame.
 */
function widgetId() {
  const raw = (import.meta.env.VITE_TRUSTINDEX_WIDGET_ID || '').trim();
  const id = raw.includes('?') ? raw.split('?').pop() : raw;
  return /^[A-Za-z0-9_-]+$/.test(id) ? id : '';
}

const WIDGET_ID = widgetId();

export default function GoogleReviews() {
  const slot = useRef(null);

  useEffect(() => {
    const node = slot.current;
    if (!WIDGET_ID || !node) return undefined;

    // The loader draws the widget where its own script tag sits, so the tag
    // goes inside this section rather than in the page head.
    const script = document.createElement('script');
    script.src = `https://cdn.trustindex.io/loader.js?${WIDGET_ID}`;
    script.defer = true;
    script.async = true;
    node.appendChild(script);

    return () => {
      node.innerHTML = '';
    };
  }, []);

  if (!WIDGET_ID) return null;

  return (
    <section className="section section-alt" aria-labelledby="lp-reviews-title">
      <div className="container">
        <div className="section-head">
          <span className="section-eyebrow">Reviews</span>
          <h2 id="lp-reviews-title" className="section-title">What people say</h2>
        </div>
        <div ref={slot} className="lp-reviews-widget" />
      </div>
    </section>
  );
}
