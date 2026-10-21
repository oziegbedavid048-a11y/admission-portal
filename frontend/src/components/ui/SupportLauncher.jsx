import { useEffect, useRef, useState } from 'react';
import { support } from '../../api/endpoints';
import Icon from '../../lib/icons';
import { openLiveChat } from '../../lib/liveChat';

/**
 * The Support button at the bottom of the applicant and agent portals.
 *
 * Tapping it raises two icons in a column above it, WhatsApp and Live chat,
 * with no card around them.
 * WhatsApp then shows one WhatsApp icon per country number set in the admin
 * (Nigeria now; Ghana and Gambia appear as soon as their numbers are added),
 * and tapping one opens WhatsApp with that number. Live chat opens the chat
 * window.
 *
 * The button can be dragged anywhere on the screen, so it never has to sit on
 * top of text or another button. Where it was left is remembered on this
 * device. A short tap still opens the menu; only a real drag moves it.
 */

const POSITION_KEY = 'gabstep_support_position';
const EDGE = 8; // never closer than this to the edge of the screen
const DRAG_THRESHOLD = 6; // pixels a finger may wander and still count as a tap

function readPosition() {
  try {
    const saved = JSON.parse(localStorage.getItem(POSITION_KEY) || 'null');
    if (saved && Number.isFinite(saved.right) && Number.isFinite(saved.bottom)) return saved;
  } catch {
    // Storage blocked or unreadable: the button starts in its corner.
  }
  return null;
}

function savePosition(position) {
  try {
    localStorage.setItem(POSITION_KEY, JSON.stringify(position));
  } catch {
    // Not remembered this time; it still moves.
  }
}

/** Keep the button whole and on screen, whatever the window size. */
function clamp(position, size) {
  const maxRight = Math.max(EDGE, window.innerWidth - size.width - EDGE);
  const maxBottom = Math.max(EDGE, window.innerHeight - size.height - EDGE);
  return {
    right: Math.min(Math.max(position.right, EDGE), maxRight),
    bottom: Math.min(Math.max(position.bottom, EDGE), maxBottom),
  };
}
export default function SupportLauncher({ visitor }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState('menu');
  const [numbers, setNumbers] = useState(null);
  const [chatFailed, setChatFailed] = useState(false);
  const panel = useRef(null);
  const button = useRef(null);
  const [position, setPosition] = useState(readPosition);
  const drag = useRef(null);
  const justDragged = useRef(false);

  // The closed button's size. It narrows to a round close button when open,
  // and that must not move it.
  const closedSize = useRef({ width: 120, height: 52 });
  const buttonSize = () => {
    const rect = button.current?.getBoundingClientRect();
    if (rect && rect.width && !open) closedSize.current = { width: rect.width, height: rect.height };
    return closedSize.current;
  };

  // A smaller window (a phone turned, a browser resized) never leaves the
  // button off screen.
  useEffect(() => {
    if (!position) return undefined;
    const keepOnScreen = () => setPosition((current) => (current ? clamp(current, buttonSize()) : current));
    keepOnScreen();
    window.addEventListener('resize', keepOnScreen);
    return () => window.removeEventListener('resize', keepOnScreen);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(position)]);

  const onPointerDown = (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    const rect = button.current.getBoundingClientRect();
    drag.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      // Where the button's bottom-right corner sits, measured from the
      // screen's bottom-right corner.
      right: position ? position.right : window.innerWidth - rect.right,
      bottom: position ? position.bottom : window.innerHeight - rect.bottom,
      moved: false,
    };
  };

  const onPointerMove = (event) => {
    const state = drag.current;
    if (!state || state.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.startX;
    const dy = event.clientY - state.startY;
    if (!state.moved) {
      if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
      state.moved = true;
      try {
        // Keeps the drag going when the finger outruns the button.
        button.current.setPointerCapture?.(event.pointerId);
      } catch {
        // Not every pointer can be captured; the drag still works without it.
      }
      if (open) close();
    }
    event.preventDefault();
    setPosition(clamp({ right: state.right - dx, bottom: state.bottom - dy }, buttonSize()));
  };

  const onPointerUp = (event) => {
    const state = drag.current;
    if (!state || state.pointerId !== event.pointerId) return;
    drag.current = null;
    if (state.moved) {
      // The click that follows a drag is not a tap.
      justDragged.current = true;
      setPosition((current) => {
        if (current) savePosition(current);
        return current;
      });
    }
  };

  const onButtonClick = () => {
    if (justDragged.current) {
      justDragged.current = false;
      return;
    }
    if (open) close();
    else setOpen(true);
  };

  // The menu opens towards the middle of the screen: above the button when it
  // sits low, below it when it sits high, and lined up with whichever side it
  // is nearer.
  const nearTop = position ? position.bottom > window.innerHeight / 2 : false;
  const nearLeft = position ? position.right > window.innerWidth / 2 : false;
  const placement = `${nearTop ? ' is-top' : ''}${nearLeft ? ' is-left' : ''}${drag.current?.moved ? ' is-dragging' : ''}`;
  // Anchored on the side the menu opens away from, so opening it never
  // pushes the button out of the place it was left.
  let style;
  if (position) {
    const size = closedSize.current;
    style = nearTop
      ? { top: `${window.innerHeight - position.bottom - size.height}px`, bottom: 'auto' }
      : { bottom: `${position.bottom}px` };
    Object.assign(
      style,
      nearLeft
        ? { left: `${window.innerWidth - position.right - size.width}px`, right: 'auto' }
        : { right: `${position.right}px` },
    );
  }

  // The numbers are fetched each time WhatsApp is opened, so a number added in
  // the admin shows without anyone reloading the page.
  useEffect(() => {
    if (!open || view !== 'whatsapp') return undefined;
    let cancelled = false;
    support
      .whatsapp()
      .then(({ data }) => {
        if (!cancelled) setNumbers(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!cancelled) setNumbers((current) => current || []);
      });
    return () => {
      cancelled = true;
    };
  }, [open, view]);

  // Closes on Escape and on a tap outside.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') close();
    };
    const onPointer = (event) => {
      if (!panel.current?.contains(event.target) && !button.current?.contains(event.target)) close();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
    };
  }, [open]);

  const close = () => {
    setOpen(false);
    setView('menu');
    setChatFailed(false);
  };

  const startChat = async () => {
    const opened = await openLiveChat(visitor);
    if (opened) close();
    else setChatFailed(true);
  };

  return (
    <div className={`support-launcher${placement}`} style={style}>
      {open ? (
        // No card: the choices stand in a column straight above the button.
        <ul className="support-stack" ref={panel} aria-label="Contact support">
          {view === 'menu' ? (
            <>
              <li>
                <button type="button" className="support-item" onClick={() => setView('whatsapp')}>
                  <span className="support-item-label">WhatsApp</span>
                  <span className="support-item-icon is-whatsapp">
                    <WhatsAppGlyph />
                  </span>
                </button>
              </li>
              <li>
                <button type="button" className="support-item" onClick={startChat}>
                  <span className="support-item-label">
                    {chatFailed ? 'Live chat is unavailable, try WhatsApp' : 'Live chat'}
                  </span>
                  <span className="support-item-icon is-chat">
                    <Icon name="chat" size={24} />
                  </span>
                </button>
              </li>
            </>
          ) : numbers === null ? (
            <li className="support-item-note">
              <span className="spinner-sm" aria-hidden="true" /> Loading
            </li>
          ) : numbers.length === 0 ? (
            <li className="support-item-note">WhatsApp is not available right now</li>
          ) : (
            // One WhatsApp icon per country number set in the admin.
            numbers.map((number) => (
              <li key={number.country}>
                <a
                  className="support-item"
                  href={number.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={close}
                  aria-label={`WhatsApp ${number.country}, ${number.phone}`}
                >
                  <span className="support-item-label">{number.country}</span>
                  <span className="support-item-icon is-whatsapp">
                    <WhatsAppGlyph />
                  </span>
                </a>
              </li>
            ))
          )}
        </ul>
      ) : null}

      <button
        ref={button}
        type="button"
        className={`support-button${open ? ' is-open' : ''}`}
        onClick={onButtonClick}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        aria-expanded={open}
        aria-label={open ? 'Close support' : 'Support'}
        title={open ? undefined : 'Support. Drag to move it.'}
      >
        <Icon name={open ? 'close' : 'headset'} size={24} />
        {open ? null : <span className="support-button-label">Support</span>}
      </button>
    </div>
  );
}

function WhatsAppGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.86 9.86 0 0 0 4.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91A9.86 9.86 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24a8.2 8.2 0 0 1 8.24 8.25c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.12-.15.16-.25.25-.42.08-.17.04-.31-.02-.44-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.23.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.29Z"
      />
    </svg>
  );
}
