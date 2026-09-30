import { useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { applications } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { compressImageFile } from '../../lib/compress';

/**
 * Uploads a new copy of one document. Shown beside a document the admissions
 * desk rejected; the copy goes straight back into review.
 */
export default function DocumentReplaceButton({ reference, documentId, onReplaced }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const upload = async (event) => {
    const picked = event.target.files?.[0];
    event.target.value = '';
    if (!picked) return;
    setBusy(true);
    setError('');
    try {
      const file = await compressImageFile(picked);
      await applications.replaceDocument(reference, documentId, file);
      await onReplaced?.();
    } catch (err) {
      setError(errorMessage(err, 'The file could not be uploaded. Try again.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="doc-replace">
      <input
        ref={input}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,application/pdf,image/*"
        hidden
        onChange={upload}
      />
      <button
        type="button"
        className="g-btn g-btn-primary g-btn-sm"
        onClick={() => input.current?.click()}
        disabled={busy}
        aria-busy={busy}
      >
        {busy ? <span className="spinner-sm" aria-hidden="true" /> : <Icon name="upload" size={14} />}
        <span>{busy ? 'Uploading' : 'Upload a replacement'}</span>
      </button>
      {error ? <p className="doc-replace-error" role="alert">{error}</p> : null}
    </div>
  );
}
