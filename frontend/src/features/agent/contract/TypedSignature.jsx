import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { INK } from './SignaturePad';

// Three handwriting styles. Loaded from Google Fonts only when this page opens.
export const STYLES = [
  { id: 'great-vibes', family: 'Great Vibes', weight: 400, size: 1 },
  { id: 'dancing-script', family: 'Dancing Script', weight: 600, size: 0.82 },
  { id: 'allura', family: 'Allura', weight: 400, size: 1.05 },
];

const FONT_LINK_ID = 'gabstep-signature-fonts';

let fontsReady = null;

/** Add the handwriting fonts' stylesheet once; resolves when the faces load. */
function loadFonts() {
  if (fontsReady) return fontsReady;
  fontsReady = new Promise((resolve) => {
    let link = document.getElementById(FONT_LINK_ID);
    const faces = () =>
      Promise.all(STYLES.map((style) => document.fonts.load(`${style.weight} 40px "${style.family}"`)))
        .catch(() => null)
        .then(resolve);
    if (link) {
      faces();
      return;
    }
    link = document.createElement('link');
    link.id = FONT_LINK_ID;
    link.rel = 'stylesheet';
    link.href =
      'https://fonts.googleapis.com/css2?family=Allura&family=Dancing+Script:wght@600&family=Great+Vibes&display=swap';
    // The faces can only be requested once the stylesheet has declared them.
    link.onload = faces;
    link.onerror = () => resolve();
    document.head.appendChild(link);
  });
  return fontsReady;
}

/** Draw `name` in a handwriting style as a transparent PNG data URL. */
export async function renderTypedSignature(name, styleId) {
  const style = STYLES.find((item) => item.id === styleId) || STYLES[0];
  // If the font cannot load, the browser's own cursive face is used.
  await loadFonts();
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 300;
  const context = canvas.getContext('2d');
  let size = Math.round(150 * style.size);
  // Shrink a long name until it fits with a margin either side.
  const fit = () => {
    context.font = `${style.weight} ${size}px "${style.family}", cursive`;
    return context.measureText(name).width;
  };
  while (fit() > canvas.width - 80 && size > 40) size -= 6;
  context.fillStyle = INK;
  context.textBaseline = 'middle';
  context.textAlign = 'center';
  context.fillText(name, canvas.width / 2, canvas.height / 2 + size * 0.08);
  return canvas.toDataURL('image/png');
}

/**
 * "Use my name as my signature": the agent's name, written out in the style
 * they pick. The name can be edited, so a shorter form can be used.
 */
export default function TypedSignature({ name, onNameChange, styleId, onStyleChange }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadFonts().then(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const shown = name.trim() || 'Your name';

  return (
    <div className="sig-typed">
      <div className="agent-form-group">
        <label className="agent-form-label" htmlFor="sig-typed-name">
          Name to sign with
        </label>
        <input
          id="sig-typed-name"
          className="agent-form-control"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          maxLength={80}
          autoComplete="name"
        />
      </div>

      <div className="sig-styles" role="radiogroup" aria-label="Signature style">
        {STYLES.map((style) => {
          const active = style.id === styleId;
          return (
            <button
              key={style.id}
              type="button"
              role="radio"
              aria-checked={active}
              className={`sig-style ${active ? 'is-active' : ''} ${ready ? '' : 'is-loading'}`.trim()}
              onClick={() => onStyleChange(style.id)}
            >
              <FittedSample text={shown} style={style} ready={ready} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** The name as large as the tile allows, up to the style's natural size. */
function FittedSample({ text, style, ready }) {
  const span = useRef(null);
  const [size, setSize] = useState(34 * style.size);

  useLayoutEffect(() => {
    const element = span.current;
    const tile = element?.parentElement;
    if (!element || !tile) return undefined;
    const fit = () => {
      // Width scales with font size, so the width at the largest size is
      // worked out from the current one; the element is never resized here.
      const largest = 34 * style.size;
      const current = parseFloat(element.style.fontSize) || largest;
      const room = tile.clientWidth - 28;
      const needed = (element.scrollWidth * largest) / current;
      setSize(needed > room && needed > 0 ? Math.max(14, Math.floor((largest * room) / needed)) : largest);
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(tile);
    // A handwriting face arriving changes the width of the same text.
    document.fonts?.addEventListener?.('loadingdone', fit);
    document.fonts?.ready?.then(fit);
    return () => {
      observer.disconnect();
      document.fonts?.removeEventListener?.('loadingdone', fit);
    };
  }, [text, style.size, ready]);

  return (
    <span
      ref={span}
      className="sig-style-sample"
      style={{ fontFamily: `"${style.family}", cursive`, fontWeight: style.weight, fontSize: `${size}px` }}
    >
      {text}
    </span>
  );
}
