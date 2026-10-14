import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';

// Dark blue ink, the colour of the company's own signature on the contract.
export const INK = '#1e3a8a';

/**
 * A signature drawn with a finger, a stylus or a mouse.
 *
 * Pointer events cover all three. Strokes are kept as points so the drawing
 * survives a resize (a phone turned on its side) and is redrawn sharp at the
 * screen's pixel density. The line thins as the pen moves faster, which is what
 * makes it read as handwriting rather than a drawing.
 *
 * The parent reads it through a ref: isEmpty(), clear() and toDataURL(), which
 * returns a transparent PNG of the ink only.
 */
const SignaturePad = forwardRef(function SignaturePad({ onChange, label = 'Draw your signature' }, ref) {
  const canvas = useRef(null);
  const strokes = useRef([]);
  const current = useRef(null);
  const [empty, setEmpty] = useState(true);

  const redraw = useCallback(() => {
    const element = canvas.current;
    if (!element) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 3);
    const { width, height } = element.getBoundingClientRect();
    if (element.width !== Math.round(width * ratio) || element.height !== Math.round(height * ratio)) {
      element.width = Math.round(width * ratio);
      element.height = Math.round(height * ratio);
    }
    const context = element.getContext('2d');
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.strokeStyle = INK;
    context.fillStyle = INK;
    strokes.current.forEach((stroke) => drawStroke(context, stroke, width, height));
  }, []);

  useEffect(() => {
    redraw();
    const observer = new ResizeObserver(() => redraw());
    if (canvas.current) observer.observe(canvas.current);
    return () => observer.disconnect();
  }, [redraw]);

  const point = (event) => {
    const box = canvas.current.getBoundingClientRect();
    // Stored as fractions of the pad, so a resize scales the drawing with it.
    return { x: (event.clientX - box.left) / box.width, y: (event.clientY - box.top) / box.height, t: event.timeStamp };
  };

  const start = (event) => {
    if (event.button !== undefined && event.button > 0) return;
    event.preventDefault();
    try {
      canvas.current.setPointerCapture?.(event.pointerId);
    } catch {
      // Some browsers refuse capture for a pointer that has just lifted. The
      // stroke is still drawn; it only ends on release inside the pad.
    }
    current.current = [point(event)];
    strokes.current.push(current.current);
    redraw();
  };

  const move = (event) => {
    if (!current.current) return;
    event.preventDefault();
    const events = event.getCoalescedEvents ? event.getCoalescedEvents() : [event];
    events.forEach((item) => current.current.push(point(item)));
    redraw();
  };

  const end = () => {
    if (!current.current) return;
    current.current = null;
    // An accidental tap leaves a dot, not a signature: it is taken off again,
    // and the pad counts as signed only once there is a real line on it.
    strokes.current = strokes.current.filter((stroke) => strokeLength(stroke, canvas.current) >= MIN_STROKE_PX);
    redraw();
    const inked = inkLength(strokes.current, canvas.current) >= MIN_SIGNATURE_PX;
    setEmpty(strokes.current.length === 0);
    onChange?.(inked);
  };

  useImperativeHandle(ref, () => ({
    isEmpty: () => strokes.current.length === 0,
    clear: () => {
      strokes.current = [];
      current.current = null;
      setEmpty(true);
      onChange?.(false);
      redraw();
    },
    toDataURL: () => {
      // Drawn again on a large off-screen canvas, so the image on the
      // contract is crisp whatever size the pad was on screen.
      const box = canvas.current.getBoundingClientRect();
      const scale = 1200 / Math.max(box.width, 1);
      const out = document.createElement('canvas');
      out.width = 1200;
      out.height = Math.round(box.height * scale);
      const context = out.getContext('2d');
      context.scale(scale, scale);
      context.lineCap = 'round';
      context.lineJoin = 'round';
      context.strokeStyle = INK;
      context.fillStyle = INK;
      // A heavier pen than on screen: on the contract the signature is printed
      // small, and a hairline would not survive it.
      strokes.current.forEach((stroke) => drawStroke(context, stroke, box.width, box.height, EXPORT_PEN));
      return out.toDataURL('image/png');
    },
  }));

  return (
    <div className="sig-pad">
      <canvas
        ref={canvas}
        className="sig-pad-canvas"
        role="img"
        aria-label={empty ? `${label}. The signature box is empty.` : `${label}. You have signed.`}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        onPointerLeave={end}
      />
      <div className="sig-pad-line" aria-hidden="true" />
      {empty ? (
        <span className="sig-pad-placeholder" aria-hidden="true">
          Sign here
        </span>
      ) : null}
    </div>
  );
});

// A stroke shorter than this is a tap. A signature needs this much line in all.
const EXPORT_PEN = 1.8;
const MIN_STROKE_PX = 6;
const MIN_SIGNATURE_PX = 60;

function strokeLength(stroke, element) {
  const box = element.getBoundingClientRect();
  let length = 0;
  for (let i = 1; i < stroke.length; i += 1) {
    length += Math.hypot((stroke[i].x - stroke[i - 1].x) * box.width, (stroke[i].y - stroke[i - 1].y) * box.height);
  }
  return length;
}

function inkLength(strokes, element) {
  return strokes.reduce((total, stroke) => total + strokeLength(stroke, element), 0);
}

function drawStroke(context, stroke, width, height, pen = 1) {
  const points = stroke.map((p) => ({ x: p.x * width, y: p.y * height, t: p.t }));
  if (points.length === 1) {
    context.beginPath();
    context.arc(points[0].x, points[0].y, 1.4 * pen, 0, Math.PI * 2);
    context.fill();
    return;
  }
  let lineWidth = 2.6;
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1];
    const b = points[i];
    const distance = Math.hypot(b.x - a.x, b.y - a.y);
    const time = Math.max(b.t - a.t, 1);
    // Faster strokes are thinner, eased so the width never jumps.
    const target = Math.max(1.2, Math.min(3.2, 3.4 - (distance / time) * 1.1));
    lineWidth = lineWidth * 0.7 + target * 0.3;
    const previous = points[i - 2] || a;
    const midStart = { x: (previous.x + a.x) / 2, y: (previous.y + a.y) / 2 };
    const midEnd = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    context.beginPath();
    context.lineWidth = lineWidth * pen;
    context.moveTo(midStart.x, midStart.y);
    context.quadraticCurveTo(a.x, a.y, midEnd.x, midEnd.y);
    context.stroke();
  }
  const last = points[points.length - 1];
  const beforeLast = points[points.length - 2];
  context.beginPath();
  context.moveTo((beforeLast.x + last.x) / 2, (beforeLast.y + last.y) / 2);
  context.lineTo(last.x, last.y);
  context.stroke();
}

export default SignaturePad;
