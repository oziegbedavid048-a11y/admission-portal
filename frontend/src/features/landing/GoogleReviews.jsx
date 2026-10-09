import { useCallback, useEffect, useRef, useState } from 'react';
import Icon from '../../lib/icons';

/**
 * Google reviews on the home page, laid out like a review widget: a sliding
 * row of cards that moves on by one every few seconds, and a link out to the
 * full list on Google.
 *
 * The reviews are copied by hand from Gabstep's Google profile, so the section
 * costs nothing to run and depends on no outside service. To add a new one,
 * copy it from Google into REVIEWS word for word.
 */
const REVIEWS = [
  {
    name: 'samson otokurin',
    rating: 5,
    text:
      'Excellent service from Gabstep! They assisted me with my admission application and delivered fast and genuine support. Highly recommended for their efficiency and reliability.',
    color: '#0b5d3b',
  },
  {
    name: 'Chigozie George Iwuchukwu',
    rating: 5,
    text: 'I applied through them and admission was offered to me and we are ongoing other processes.',
    color: '#e8710a',
  },
  {
    name: 'Simeon Adewale',
    rating: 5,
    text:
      'I contacted Gabstep online and was impressed with their response and professionalism. They Answered my questions and guided me through the process.',
    color: '#c2185b',
  },
  {
    name: 'Henry Anoribe',
    rating: 4,
    text: 'Excellent service! My Admission and Visa process was smooth and fast. Highly recommend them for anyone',
    color: '#d81b60',
  },
  {
    name: 'Chukwuebukasamuel',
    rating: 4,
    text: 'They are professional and have reliable service. They assisted me with my Admission process',
    color: '#7b1fa2',
  },
  {
    name: 'Dagbaesinam',
    rating: 4,
    text:
      "Even though we never met physically and don't know there office, they delivered and was transparent throughout the whole process.",
    color: '#33691e',
  },
  {
    name: 'Friday omorogbe',
    rating: 4,
    text: 'I Appreciate the support i received during my visa process.',
    color: '#78909c',
  },
];

const ALL_REVIEWS_URL = 'https://www.google.com/search?q=gabstep+reviews';
const SLIDE_EVERY_MS = 5000;

function GoogleMark({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

function Stars({ rating }) {
  return (
    <span className="lp-review-stars" role="img" aria-label={`${rating} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <svg key={n} width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" className={n <= rating ? 'on' : ''}>
          <path d="M12 2.5l2.94 5.96 6.56.95-4.75 4.63 1.12 6.54L12 17.5l-5.87 3.08 1.12-6.54L2.5 9.41l6.56-.95z" />
        </svg>
      ))}
    </span>
  );
}

export const HAS_REVIEWS = REVIEWS.length > 0;

export default function GoogleReviews() {
  const track = useRef(null);
  const [paused, setPaused] = useState(false);

  // Moves the row by one card, or back to the start after the last one.
  const step = useCallback((direction) => {
    const node = track.current;
    if (!node || !node.firstElementChild) return;
    const card = node.firstElementChild.getBoundingClientRect().width;
    const gap = parseFloat(getComputedStyle(node).columnGap) || 0;
    const width = card + gap;
    const last = node.scrollWidth - node.clientWidth - 2;
    let target = node.scrollLeft + direction * width;
    if (direction > 0 && node.scrollLeft >= last) target = 0;
    if (direction < 0 && node.scrollLeft <= 2) target = node.scrollWidth;
    node.scrollTo({ left: target, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (paused || reduced) return undefined;
    const timer = window.setInterval(() => {
      if (!document.hidden) step(1);
    }, SLIDE_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [paused, step]);

  if (!HAS_REVIEWS) return null;

  return (
    <section id="reviews" className="lp-section" aria-labelledby="lp-reviews-title">
      <div className="container">
        <header className="lp-head reveal">
          <p className="lp-eyebrow">Reviews</p>
          <h2 id="lp-reviews-title" className="lp-title">Trusted by students and families.</h2>
        </header>

        <div
          className="lp-reviews reveal"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          onFocus={() => setPaused(true)}
          onBlur={() => setPaused(false)}
          onTouchStart={() => setPaused(true)}
          onTouchEnd={() => setPaused(false)}
        >
          <ul ref={track} className="lp-reviews-track">
            {REVIEWS.map((review) => (
              <li key={review.name} className="lp-review">
                <div className="lp-review-head">
                  <span className="lp-review-avatar" style={{ background: review.color }} aria-hidden="true">
                    {review.name.charAt(0)}
                  </span>
                  <div className="lp-review-who">
                    <strong>{review.name}</strong>
                    <Stars rating={review.rating} />
                  </div>
                  <GoogleMark />
                </div>
                <p>{review.text}</p>
              </li>
            ))}
          </ul>

          <div className="lp-reviews-nav">
            <button type="button" aria-label="Previous review" onClick={() => step(-1)}>
              <Icon name="chevronLeft" size={20} strokeWidth={2} />
            </button>
            <button type="button" aria-label="Next review" onClick={() => step(1)}>
              <Icon name="chevronRight" size={20} strokeWidth={2} />
            </button>
          </div>
        </div>

        <div className="lp-cta reveal">
          <a href={ALL_REVIEWS_URL} target="_blank" rel="noopener noreferrer" className="lp-btn">
            See more Google reviews
            <Icon name="arrowRight" size={18} strokeWidth={2} interactive={false} />
          </a>
        </div>
      </div>
    </section>
  );
}
