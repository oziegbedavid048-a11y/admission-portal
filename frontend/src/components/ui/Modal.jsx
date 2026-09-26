import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import Icon from '../../lib/icons';

/**
 * A sheet that rises from the bottom of the screen.
 *
 * Every dialog in the product is this one component, and all of them arrive the
 * same way: the sheet slides up from under the viewport, the header and footer
 * stay put, and only the middle scrolls. A dialog on a phone is reached with a
 * thumb, so the actions sit at the bottom of the screen rather than the top, and
 * the sheet never grows past the viewport: a long form scrolls inside itself
 * instead of pushing its own buttons out of reach.
 *
 * It closes on Escape and on a backdrop press, keeps focus inside itself while
 * open, and gives the page its scrollbar back when it closes.
 *
 * `variant` is kept for the callers that pass it, but it no longer picks a
 * different stylesheet: it only tags the sheet so portal-specific type and
 * button styles still apply inside. There is one sheet, styled in one place.
 */
export default function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  variant = 'site',
  size,
  labelledBy,
  dismissable = true,
  className = '',
}) {
  const panelRef = useRef(null);
  const restoreFocusTo = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    restoreFocusTo.current = document.activeElement;
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (event) => {
      if (event.key === 'Escape' && dismissable) {
        onClose?.();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;

      const focusable = panelRef.current.querySelectorAll(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    const timer = window.setTimeout(() => {
      const target = panelRef.current?.querySelector(
        'input:not([type="hidden"]), select, textarea, button',
      );
      target?.focus();
    }, 40);

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      window.clearTimeout(timer);
      document.body.style.overflow = overflow;
      restoreFocusTo.current?.focus?.();
    };
  }, [open, onClose, dismissable]);

  if (!open) return null;

  return createPortal(
    <div
      className="sheet-scrim"
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledBy}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && dismissable) onClose?.();
      }}
    >
      <div
        className={`sheet sheet-${variant} ${className}`.trim()}
        ref={panelRef}
        style={size ? { maxWidth: size } : undefined}
      >
        {/* The grabber says which edge the sheet came from and which way it
            goes back, on a sheet that has no visible title to say it. */}
        <div className="sheet-grabber" aria-hidden="true" />

        {title ? (
          <div className="sheet-header">
            <div className="sheet-heading">
              <h3 id={labelledBy}>{title}</h3>
              {subtitle ? <span className="sheet-subtitle">{subtitle}</span> : null}
            </div>
            {dismissable ? (
              <button
                type="button"
                className="sheet-close"
                onClick={onClose}
                aria-label="Close"
              >
                <Icon name="close" size={18} strokeWidth={2.2} />
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="sheet-body">{children}</div>

        {footer ? <div className="sheet-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
