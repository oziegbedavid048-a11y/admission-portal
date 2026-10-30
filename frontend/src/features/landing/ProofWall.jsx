import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { catalog } from '../../api/endpoints';
import Icon from '../../lib/icons';

/**
 * Visas and offer letters Gabstep students received, shown above the Google
 * reviews as one compact row of same-sized cards. Tapping a card opens it
 * larger, with previous and next.
 *
 * The cards come from the admin ("Landing page review images"), where every
 * upload goes through a blur tool: names, addresses, student IDs, passport and
 * document numbers and the machine-readable lines are blurred before anything
 * is stored. With none to show, the row is left out.
 */
// Which part of an image a card shows when it has to crop (set per image in the admin).
const FOCUS = { top: 'center top', center: 'center 55%', bottom: 'center bottom' };

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'visa', label: 'Visas' },
  { id: 'offer', label: 'Offer letters' },
];

const SLIDE_EVERY_MS = 3000;

// Photos (a visa collected at the office) count with the visas.
const inFilter = (item, id) => id === 'all' || item.kind === id || (id === 'visa' && item.kind === 'photo');

export default function ProofWall() {
  const track = useRef(null);
  const [filter, setFilter] = useState('all');
  const [open, setOpen] = useState(-1);
  const [paused, setPaused] = useState(false);
  const [proof, setProof] = useState([]);
  const items = useMemo(() => proof.filter((item) => inFilter(item, filter)), [proof, filter]);
  const count = (id) => proof.filter((item) => inFilter(item, id)).length;

  useEffect(() => {
    let cancelled = false;
    catalog
      .landingReviews()
      .then(({ data }) => {
        if (!cancelled) setProof(Array.isArray(data) ? data : []);
      })
      .catch(() => null);
    return () => {
      cancelled = true;
    };
  }, []);

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

  if (!proof.length) return null;

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
            <li key={item.id} className={`lp-proof-card is-${item.kind}`}>
              <button type="button" onClick={() => setOpen(index)} aria-label={`View ${item.title}, ${item.detail}`}>
                <img
                  src={item.image}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  style={item.kind === 'offer' ? undefined : { objectPosition: FOCUS[item.focus] || FOCUS.top }}
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
        <img src={item.image} alt={`${item.title}, ${item.detail}`} />
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
