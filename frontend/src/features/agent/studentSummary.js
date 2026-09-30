import { partners } from '../../api/endpoints';

/** Downloads the one-page student summary PDF for a paid application. */
export async function downloadStudentSummary(reference) {
  const { data } = await partners.studentSummary(reference);
  const url = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${reference}-student-summary.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}
