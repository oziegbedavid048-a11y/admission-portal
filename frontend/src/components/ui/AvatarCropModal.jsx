import { useCallback, useEffect, useRef, useState } from 'react';
import Modal from './Modal';

/**
 * Frame a new profile picture before it is uploaded.
 *
 * The chosen image sits under a circle the size the photo is shown at. The
 * person drags it to position it and zooms with the slider (or the mouse wheel,
 * or + and - and the arrow keys), and Done hands back exactly what is inside the
 * circle as a square JPEG.
 *
 * Redrawing the picture here is also what lets any image the browser can show
 * be used. Pictures saved by AI tools often arrive as AVIF, WebP or HEIC, which
 * the server's image check refused as "not a valid image"; the crop is always
 * sent as a plain JPEG.
 */

const STAGE = 280; // the circle, in CSS pixels
const OUTPUT = 512; // the uploaded square, in pixels
const MAX_ZOOM = 4;

function clampOffset(offset, size, zoom) {
  if (!size) return offset;
  const base = Math.max(STAGE / size.width, STAGE / size.height);
  const width = size.width * base * zoom;
  const height = size.height * base * zoom;
  const maxX = Math.max(0, (width - STAGE) / 2);
  const maxY = Math.max(0, (height - STAGE) / 2);
  return {
    x: Math.min(maxX, Math.max(-maxX, offset.x)),
    y: Math.min(maxY, Math.max(-maxY, offset.y)),
  };
}

export default function AvatarCropModal({ file, open, onCancel, onConfirm }) {
  const [url, setUrl] = useState(null);
  const [size, setSize] = useState(null);
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [saving, setSaving] = useState(false);
  const imageRef = useRef(null);
  const drag = useRef(null);

  useEffect(() => {
    if (!file) return undefined;
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    setSize(null);
    setFailed(false);
    setZoom(1);
    setOffset({ x: 0, y: 0 });
    setSaving(false);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  const setZoomClamped = useCallback(
    (next) => {
      const value = Math.min(MAX_ZOOM, Math.max(1, next));
      setZoom(value);
      setOffset((current) => clampOffset(current, size, value));
    },
    [size],
  );

  const onPointerDown = (event) => {
    if (!size) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, start: offset };
  };

  const onPointerMove = (event) => {
    if (!drag.current) return;
    const next = {
      x: drag.current.start.x + (event.clientX - drag.current.x),
      y: drag.current.start.y + (event.clientY - drag.current.y),
    };
    setOffset(clampOffset(next, size, zoom));
  };

  const endDrag = () => {
    drag.current = null;
  };

  const onWheel = (event) => {
    if (!size) return;
    setZoomClamped(zoom - event.deltaY * 0.0015);
  };

  const onKeyDown = (event) => {
    const step = 12;
    const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    if (moves[event.key]) {
      event.preventDefault();
      const [dx, dy] = moves[event.key];
      setOffset((current) => clampOffset({ x: current.x + dx, y: current.y + dy }, size, zoom));
    } else if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      setZoomClamped(zoom + 0.1);
    } else if (event.key === '-') {
      event.preventDefault();
      setZoomClamped(zoom - 0.1);
    }
  };

  const confirm = async () => {
    const image = imageRef.current;
    if (!image || !size) return;
    setSaving(true);
    const base = Math.max(STAGE / size.width, STAGE / size.height);
    const scale = base * zoom;
    const left = STAGE / 2 + offset.x - (size.width * scale) / 2;
    const top = STAGE / 2 + offset.y - (size.height * scale) / 2;

    const canvas = document.createElement('canvas');
    canvas.width = OUTPUT;
    canvas.height = OUTPUT;
    const context = canvas.getContext('2d');
    // A transparent picture would turn black as a JPEG.
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, OUTPUT, OUTPUT);
    context.imageSmoothingQuality = 'high';
    context.drawImage(image, -left / scale, -top / scale, STAGE / scale, STAGE / scale, 0, 0, OUTPUT, OUTPUT);

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    if (!blob) {
      setSaving(false);
      setFailed(true);
      return;
    }
    onConfirm(new File([blob], 'profile-photo.jpg', { type: 'image/jpeg', lastModified: Date.now() }));
  };

  const base = size ? Math.max(STAGE / size.width, STAGE / size.height) : 1;
  const shownWidth = size ? size.width * base * zoom : STAGE;
  const shownHeight = size ? size.height * base * zoom : STAGE;

  return (
    <Modal
      open={open}
      onClose={saving ? undefined : onCancel}
      dismissable={!saving}
      variant="agent"
      title="Adjust photo"
      labelledBy="avatar-crop-title"
      footer={
        <>
          <button type="button" className="agent-btn agent-btn-secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button
            type="button"
            className="agent-btn agent-btn-primary"
            onClick={confirm}
            disabled={!size || failed || saving}
          >
            Done
          </button>
        </>
      }
    >
      <div className="crop">
        {failed ? (
          <p className="crop-error" role="alert">
            This picture could not be opened. Choose a JPG or PNG photo instead.
          </p>
        ) : (
          <>
            <div
              className="crop-stage"
              style={{ width: STAGE, height: STAGE }}
              role="application"
              aria-label="Photo position. Drag, or use the arrow keys to move it and plus or minus to zoom."
              tabIndex={0}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              onWheel={onWheel}
              onKeyDown={onKeyDown}
            >
              {url ? (
                <img
                  ref={imageRef}
                  src={url}
                  alt=""
                  draggable={false}
                  className="crop-image"
                  style={{
                    width: shownWidth,
                    height: shownHeight,
                    transform: `translate(calc(-50% + ${offset.x}px), calc(-50% + ${offset.y}px))`,
                    opacity: size ? 1 : 0,
                  }}
                  onLoad={(event) =>
                    setSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })
                  }
                  onError={() => setFailed(true)}
                />
              ) : null}
              <span className="crop-mask" aria-hidden="true" />
              {!size ? <span className="crop-loading spinner" aria-hidden="true" /> : null}
            </div>

            <label className="crop-zoom">
              <span className="crop-zoom-label">Zoom</span>
              <input
                type="range"
                min="1"
                max={MAX_ZOOM}
                step="0.01"
                value={zoom}
                onChange={(event) => setZoomClamped(Number(event.target.value))}
                disabled={!size}
              />
            </label>
          </>
        )}
      </div>
    </Modal>
  );
}
