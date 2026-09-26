import { useCallback, useEffect, useRef, useState } from 'react';

const ROTATION_MS = 6000;

const SLIDES = [
  'https://images.unsplash.com/photo-1541339907198-e08756dedf3f?q=80&w=1600&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?q=80&w=1600&auto=format&fit=crop',
  'https://images.unsplash.com/photo-1562774053-701939374585?q=80&w=1600&auto=format&fit=crop',
];

/**
 * The hero's crossfading background. It pauses while the pointer is over the
 * hero, and it does not rotate at all for a visitor who has asked for reduced
 * motion — a slow crossfade behind text is exactly what that setting is for.
 */
export default function HeroCarousel({ children }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const reducedMotion = useRef(
    typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  const show = useCallback((next) => {
    setIndex(((next % SLIDES.length) + SLIDES.length) % SLIDES.length);
  }, []);

  useEffect(() => {
    if (paused || reducedMotion.current) return undefined;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % SLIDES.length);
    }, ROTATION_MS);
    return () => window.clearInterval(timer);
  }, [paused]);

  return (
    <section
      className="hero-section"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="hero-carousel">
        {SLIDES.map((url, slideIndex) => (
          <div
            key={url}
            className={`carousel-slide ${slideIndex === index ? 'active' : ''}`.trim()}
            style={{ backgroundImage: `url('${url}')` }}
          />
        ))}
      </div>

      <div className="hero-overlay" />

      <div className="container hero-content-wrap">{children}</div>

      <div className="carousel-controls" aria-label="Choose a background image">
        {SLIDES.map((url, slideIndex) => (
          <button
            key={url}
            type="button"
            className={`carousel-dot ${slideIndex === index ? 'active' : ''}`.trim()}
            aria-label={`Show image ${slideIndex + 1} of ${SLIDES.length}`}
            aria-current={slideIndex === index}
            onClick={() => show(slideIndex)}
          />
        ))}
      </div>
    </section>
  );
}
