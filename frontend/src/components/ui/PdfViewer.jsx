import { useEffect, useRef, useState } from 'react';
import Icon from '../../lib/icons';

/**
 * Shows a PDF inside the page, on every device.
 *
 * An <iframe> only works where the browser has a built-in PDF viewer. Phone
 * browsers do not: Android Chrome showed an "Open" button that left the site
 * for another app. This draws each page with pdf.js onto a canvas instead, so
 * a PDF reads in the page exactly as an image does. pdf.js is loaded only when
 * a PDF is opened, so it adds nothing to pages that never show one.
 */
export default function PdfViewer({ url, title = 'Document' }) {
  const holder = useRef(null);
  const [state, setState] = useState('loading');
  const [pages, setPages] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let task = null;
    const target = holder.current;

    (async () => {
      try {
        const pdfjs = await import('pdfjs-dist');
        const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default;

        // Whole-file fetch: the backend answers with the full document, and range
        // requests would only add a cross-origin preflight for nothing.
        task = pdfjs.getDocument({ url, withCredentials: false, disableRange: true, disableStream: true });
        const pdf = await task.promise;
        if (cancelled || !target) return;
        setPages(pdf.numPages);
        target.innerHTML = '';

        const width = Math.max(280, target.clientWidth || 600);
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        for (let number = 1; number <= pdf.numPages; number += 1) {
          const page = await pdf.getPage(number);
          if (cancelled) return;
          const base = page.getViewport({ scale: 1 });
          const scale = width / base.width;
          const viewport = page.getViewport({ scale: scale * ratio });
          const canvas = document.createElement('canvas');
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.style.width = `${Math.floor(viewport.width / ratio)}px`;
          canvas.style.height = `${Math.floor(viewport.height / ratio)}px`;
          canvas.className = 'pdf-page';
          canvas.setAttribute('role', 'img');
          canvas.setAttribute('aria-label', `${title}, page ${number} of ${pdf.numPages}`);
          target.appendChild(canvas);
          await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
          if (number === 1 && !cancelled) setState('ready');
        }
      } catch {
        if (!cancelled) setState('failed');
      }
    })();

    return () => {
      cancelled = true;
      task?.destroy?.();
    };
  }, [url, title]);

  return (
    <div className="pdf-viewer">
      {state === 'loading' ? (
        <div className="pdf-viewer-status" role="status">
          <span className="spinner-sm" aria-hidden="true" />
          Loading document
        </div>
      ) : null}
      {state === 'failed' ? (
        <div className="pdf-viewer-status">
          <Icon name="alert" size={20} />
          This document could not be displayed. Use Download to open it.
        </div>
      ) : null}
      <div ref={holder} className="pdf-viewer-pages" aria-label={pages ? `${title}, ${pages} pages` : undefined} />
    </div>
  );
}
