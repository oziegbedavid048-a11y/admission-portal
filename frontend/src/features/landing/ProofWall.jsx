import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Icon from '../../lib/icons';

/**
 * Visas and offer letters Gabstep students received, shown above the Google
 * reviews as one compact row of same-sized cards. Tapping a card opens it
 * larger, with previous and next.
 *
 * Every image in /public/reviews is cropped and redacted: names, addresses,
 * student IDs, passport and document numbers and the machine-readable lines
 * are blurred so they cannot be read. Never add an unredacted document here.
 */
const PROOF = [
  { src: '/reviews/office-1.webp', kind: 'visa', title: 'Visa collected', detail: 'At the Gabstep office', fit: 'center 58%' },
  { src: '/reviews/visa-1.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-1.webp', kind: 'offer', title: 'Welding and Fabrication', detail: 'Sheridan College · $2,000 scholarship' },
  { src: '/reviews/visa-3.webp', kind: 'visa', title: 'Work permit visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-5.webp', kind: 'offer', title: 'Interior Decorating', detail: 'Sheridan College · $3,000 scholarship' },
  { src: '/reviews/visa-2.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-2.webp', kind: 'offer', title: 'Healthcare Administration', detail: 'Sheridan College · $1,000 scholarship' },
  { src: '/reviews/visa-5.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-7.webp', kind: 'offer', title: 'Social Service Worker', detail: 'Sheridan College · $3,000 scholarship' },
  { src: '/reviews/visa-4.webp', kind: 'visa', title: 'Visitor visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-3.webp', kind: 'offer', title: 'Mechanical Technician', detail: 'Sheridan College · $2,000 scholarship' },
  { src: '/reviews/visa-7.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-4.webp', kind: 'offer', title: 'Supply Chain Management', detail: 'Sheridan College · $2,000 scholarship' },
  { src: '/reviews/visa-6.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2021' },
  { src: '/reviews/offer-6.webp', kind: 'offer', title: 'Personal Support Worker', detail: 'Sheridan College · $2,000 scholarship' },
  { src: '/reviews/visa-8.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-8.webp', kind: 'offer', title: 'Healthcare Administration', detail: 'Sheridan College · $3,000 scholarship' },
  { src: '/reviews/visa-9.webp', kind: 'visa', title: 'Student visa', detail: 'Canada · 2023' },
  { src: '/reviews/offer-9.webp', kind: 'offer', title: 'Welding and Fabrication', detail: 'Sheridan College · $2,000 scholarship' },
];

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'visa', label: 'Visas' },
  { id: 'offer', label: 'Offer letters' },
];

const SLIDE_EVERY_MS = 4000;

export default function ProofWall() {
  const track = useRef(null);
  const [filter, setFilter] = useState('all');
  const [open, setOpen] = useState(-1);
  const [paused, setPaused] = useState(false);
  const items = useMemo(() => PROOF.filter((item) => filter === 'all' || item.kind === filter), [filter]);
  const count = (id) => PROOF.filter((item) => id === 'all' || item.kind === id).length;

  // One card's width plus the gap: how far the arrows and the timer move.
  const step = () => {
    const node = track.current;
    if (!node || !node.firstElementChild) return 0;
    return node.firstElementChild.getBoundingClientRect().width + (parseFloat(getComputedStyle(node).columnGap) || 0);
  };

  const scrollBy = useCallback((direction) => {
    const node = track.current;
    if (!node) return;
    const atEnd = node.scrollLeft >= node.scrollWidth - node.clientWidth - 2;
    const atStart = node.scrollLeft <= 2;
    if (direction > 0 && atEnd) node.scrollTo({ left: 0, behavior: 'smooth' });
    else if (direction < 0 && atStart) node.scrollTo({ left: node.scrollWidth, behavior: 'smooth' });
    else node.scrollBy({ left: direction * step(), behavior: 'smooth' });
  }, []);

  // Drift on by one card every few seconds, unless the visitor is looking.
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (paused || reduced || open >= 0) return undefined;
    const timer = window.setInterval(() => {
      if (!document.hidden) scrollBy(1);
    }, SLIDE_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [paused, open, scrollBy]);

  useEffect(() => {
    track.current?.scrollTo({ left: 0 });
  }, [filter]);

  return (
    <div className="lp-proof reveal">
      <div className="lp-proof-bar">
        <h3 className="lp-proof-title">Visas and offers our students received</h3>
        <div className="lp-proof-filters" role="group" aria-label="Show">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`lp-proof-filter ${filter === item.id ? 'is-active' : ''}`.trim()}
              aria-pressed={filter === item.id}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
              <span>{count(item.id)}</span>
            </button>
          ))}
        </div>
      </div>

      <div
        className="lp-proof-viewport"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
        onTouchStart={() => setPaused(true)}
      >
        <button type="button" className="lp-proof-arrow is-prev" aria-label="Previous" onClick={() => scrollBy(-1)}>
          <Icon name="arrowLeft" size={18} strokeWidth={2} interactive={false} />
        </button>
        <ul ref={track} className="lp-proof-track">
          {items.map((item, index) => (
            <li key={item.src} className={`lp-proof-card is-${item.kind}`}>
              <button type="button" onClick={() => setOpen(index)} aria-label={`View ${item.title}, ${item.detail}`}>
                <img
                  src={item.src}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  style={item.fit ? { objectPosition: item.fit } : undefined}
                />
                <span className="lp-proof-caption">
                  <span className="lp-proof-tag">{item.kind === 'offer' ? 'Offer letter' : 'Approved'}</span>
                  <strong>{item.title}</strong>
                  <small>{item.detail}</small>
                </span>
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="lp-proof-arrow is-next" aria-label="Next" onClick={() => scrollBy(1)}>
          <Icon name="arrowRight" size={18} strokeWidth={2} interactive={false} />
        </button>
      </div>

      <p className="lp-proof-note">Personal details are hidden to protect our students.</p>

      {open >= 0 ? <ProofViewer items={items} index={open} onIndex={setOpen} onClose={() => setOpen(-1)} /> : null}
    </div>
  );
}

function ProofViewer({ items, index, onIndex, onClose }) {
  const item = items[index];
  const go = useCallback((delta) => onIndex((index + delta + items.length) % items.length), [index, items.length, onIndex]);
  const closeRef = useRef(null);
  const touch = useRef(null);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight') go(1);
      if (event.key === 'ArrowLeft') go(-1);
    };
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [go, onClose]);

  // Rendered on <body>: the row fades in with a transform, which would
  // otherwise hold this fixed layer inside it.
  return createPortal(
    <div
      className="lp-proof-viewer"
      role="dialog"
      aria-modal="true"
      aria-label={item.title}
      onClick={(event) => event.target === event.currentTarget && onClose()}
      onTouchStart={(event) => {
        touch.current = event.touches[0].clientX;
      }}
      onTouchEnd={(event) => {
        const start = touch.current;
        touch.current = null;
        if (start == null) return;
        const moved = event.changedTouches[0].clientX - start;
        if (Math.abs(moved) > 50) go(moved < 0 ? 1 : -1);
      }}
    >
      <button ref={closeRef} type="button" className="lp-proof-close" aria-label="Close" onClick={onClose}>
        <Icon name="close" size={20} strokeWidth={2} interactive={false} />
      </button>
      <figure>
        <img src={item.src} alt={`${item.title}, ${item.detail}`} />
        <figcaption>
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
          <small>
            {index + 1} of {items.length}
          </small>
        </figcaption>
      </figure>
      <button type="button" className="lp-proof-nav is-prev" aria-label="Previous" onClick={() => go(-1)}>
        <Icon name="arrowLeft" size={20} strokeWidth={2} interactive={false} />
      </button>
      <button type="button" className="lp-proof-nav is-next" aria-label="Next" onClick={() => go(1)}>
        <Icon name="arrowRight" size={20} strokeWidth={2} interactive={false} />
      </button>
    </div>,
    document.body,
  );
}
