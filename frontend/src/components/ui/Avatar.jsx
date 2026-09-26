import { useEffect, useRef, useState } from 'react';
import Icon from '../../lib/icons';

/**
 * A profile picture that updates the instant a new one is chosen.
 *
 * Two things used to make a new photo look like it had not saved. The upload
 * round trip meant a second or two of the old image, and the browser then cached
 * the URL, so even a reload could serve the previous file. This shows the chosen
 * file immediately from a local object URL, and hangs a version on the saved URL
 * afterwards so the cache cannot win.
 */
export default function Avatar({ src, initials, onSelect, label = 'Change photo', id }) {
  const [preview, setPreview] = useState(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const lastSaved = useRef(src);

  // Once the saved URL changes, the upload has landed and the local preview can
  // be released; until then the preview is what the person sees.
  useEffect(() => {
    if (src !== lastSaved.current) {
      lastSaved.current = src;
      setVersion((current) => current + 1);
      setPreview((current) => {
        if (current) URL.revokeObjectURL(current);
        return null;
      });
    }
  }, [src]);

  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );

  const choose = async (file) => {
    if (!file) return;

    const objectUrl = URL.createObjectURL(file);
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current);
      return objectUrl;
    });
    setBusy(true);

    try {
      await onSelect(file);
    } catch {
      // The caller reports the failure; drop the preview so the picture on
      // screen goes back to matching what is actually stored.
      URL.revokeObjectURL(objectUrl);
      setPreview(null);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  // A saved URL is cache-busted; an object URL must be left exactly as it is.
  const shown =
    preview || (src ? `${src}${src.includes('?') ? '&' : '?'}v=${version}` : null);

  return (
    <div className="profile-avatar-wrap">
      <span className={`profile-avatar ${busy ? 'is-saving' : ''}`.trim()}>
        {shown ? <img src={shown} alt="" /> : <span>{initials}</span>}
        {busy ? <span className="avatar-spinner" aria-hidden="true" /> : null}
      </span>

      <label className="profile-avatar-edit" htmlFor={id} title={label}>
        <Icon name="camera" size={16} />
        <span className="sr-only">{label}</span>
      </label>

      <input
        type="file"
        id={id}
        ref={inputRef}
        accept="image/*"
        className="sr-only"
        onChange={(event) => choose(event.target.files?.[0])}
      />
    </div>
  );
}
