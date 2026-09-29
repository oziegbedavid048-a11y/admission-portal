import { useCallback, useEffect, useRef, useState } from 'react';

const ROTATION_MS = 6000;

// Served from this site rather than hotlinked. The middle image used to be an
// Unsplash address that had been taken down, so one slide in three rendered as a
// blank panel. Two images the site owns cannot disappear the same way.
const SLIDES = ['/assets/hero/campus-1.jpg', '/assets/hero/campus-2.jpg'];

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
