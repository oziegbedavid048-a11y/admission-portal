import { useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { fileSize } from '../../lib/format';
import { compressImageFile } from '../../lib/compress';

/**
 * One document slot: click or drop a file, see what is attached, replace it.
 * Rejects anything over the size limit or outside the accepted types before
 * the file ever reaches the server.
 */
export default function Dropzone({
  icon = 'document',
  title,
  hint,
  accept = '.pdf,.jpg,.jpeg,.png',
  maxMb = 10,
  file,
  onSelect,
  onReject,
  required = true,
  buttonLabel = 'Browse or drop a file',
}) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const accepted = accept
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  const take = async (candidate) => {
    if (!candidate) return;
    const extension = `.${candidate.name.split('.').pop().toLowerCase()}`;
    if (accepted.length && !accepted.includes(extension)) {
      onReject?.(`${title} must be one of: ${accepted.join(', ')}.`);
      return;
    }
    // Compress image if applicable before checking maxMb
    const processed = await compressImageFile(candidate);
    if (processed.size > maxMb * 1024 * 1024) {
      onReject?.(`Keep ${title.toLowerCase()} under ${maxMb}MB.`);
      return;
    }
    onSelect(processed);
  };

  return (
    <div
      className={`dropzone-card ${dragging ? 'drag-active' : ''} ${file ? 'has-file' : ''}`.trim()}
      onClick={() => inputRef.current?.click()}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        take(event.dataTransfer?.files?.[0]);
      }}
    >
      <input
        type="file"
        ref={inputRef}
        className="dropzone-file-input"
        accept={accept}
        onChange={(event) => take(event.target.files?.[0])}
      />

      <Icon name={icon} size={34} className="dropzone-icon" strokeWidth={1.6} />
      <div className="dropzone-title">
        {title} {required ? <span className="dropzone-req">*</span> : null}
      </div>
      <div className="dropzone-hint">{hint}</div>
      <button type="button" className="btn btn-sm btn-secondary">
        {file ? 'Replace file' : buttonLabel}
      </button>

      <div className={`uploaded-file-tag ${file ? 'visible' : ''}`.trim()}>
        <div className="uploaded-file-info">
          <Icon name="check" size={16} className="file-status-icon" strokeWidth={2.4} />
          <div className="uploaded-file-text">
            <span className="file-name-display" title={file?.name || ''}>{file?.name || ''}</span>
            <span className="file-size-display">{file ? fileSize(file.size) : ''}</span>
          </div>
        </div>
        <span className="badge badge-success">Ready</span>
      </div>
    </div>
  );
}
