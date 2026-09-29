import { useEffect, useState } from 'react';
import { resolveMediaUrl } from '../../lib/format';

/**
 * The signed-in person's picture, or their initials when there is none.
 *
 * Every header, top bar and chip uses this one component and reads the picture
 * from the signed-in user, so a new photo saved on any profile page appears
 * everywhere at once. A picture that fails to load falls back to the initials
 * rather than showing a broken image.
 */
export default function UserAvatar({ src, initials, className = '' }) {
  const url = resolveMediaUrl(src);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [url]);

  return (
    <span className={className} aria-hidden="true">
      {url && !failed ? (
        <img src={url} alt="" onError={() => setFailed(true)} />
      ) : (
        <span>{initials || ''}</span>
      )}
    </span>
  );
}
