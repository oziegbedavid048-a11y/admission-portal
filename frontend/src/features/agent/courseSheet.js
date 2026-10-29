import { partners } from '../../api/endpoints';

/**
 * A school's course list, downloaded as a PDF or as one image.
 *
 * Both come from the same PDF the server builds, so they always match. The
 * image is that PDF drawn with pdf.js, every page stacked into one PNG, sharp
 * enough to read when shared on WhatsApp. Its size is kept under what the
 * browser allows for one picture, so a long list still downloads on a phone.
 */

// iPhones and iPads refuse a canvas bigger than about 16 million pixels;
// other browsers allow far more, so their image can be sharper.
const IS_IOS =
  typeof navigator !== 'undefined' &&
  (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1));
const MAX_PIXELS = IS_IOS ? 15_000_000 : 40_000_000;

function save(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function fetchSheet(slug) {
  const { data } = await partners.schoolCourses(slug);
  return data instanceof Blob ? data : new Blob([data], { type: 'application/pdf' });
}

export async function downloadCoursesPdf(school) {
  save(await fetchSheet(school.slug), `${school.slug}-courses.pdf`);
}

export async function downloadCoursesImage(school) {
  const blob = await fetchSheet(school.slug);
  const pdfjs = await import('pdfjs-dist');
  const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise;

  const pages = [];
  for (let number = 1; number <= pdf.numPages; number += 1) pages.push(await pdf.getPage(number));
  const base = pages.map((page) => page.getViewport({ scale: 1 }));
  const width = Math.max(...base.map((viewport) => viewport.width));
  const height = base.reduce((sum, viewport) => sum + viewport.height, 0);
  // As sharp as the phone allows: up to twice the PDF's own size.
  const scale = Math.min(2, Math.sqrt(MAX_PIXELS / (width * height)));

  const canvas = document.createElement('canvas');
  canvas.width = Math.floor(width * scale);
  canvas.height = Math.floor(height * scale);
  const context = canvas.getContext('2d');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);

  let top = 0;
  for (const page of pages) {
    const viewport = page.getViewport({ scale });
    const sheet = document.createElement('canvas');
    sheet.width = Math.floor(viewport.width);
    sheet.height = Math.floor(viewport.height);
    await page.render({ canvasContext: sheet.getContext('2d'), viewport }).promise;
    context.drawImage(sheet, 0, top);
    top += sheet.height;
  }

  const png = await new Promise((resolve, reject) =>
    canvas.toBlob((result) => (result ? resolve(result) : reject(new Error('Could not make the image.'))), 'image/png'),
  );
  save(png, `${school.slug}-courses.png`);
}
