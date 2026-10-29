import { useState } from 'react';
import { errorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';
import { downloadCoursesImage, downloadCoursesPdf } from './courseSheet';

/** Download the open school's course list, as a PDF or as one image. */
export default function CourseSheetDownload({ school }) {
  const toast = useToast();
  const [busy, setBusy] = useState('');

  const run = async (kind) => {
    setBusy(kind);
    try {
      await (kind === 'pdf' ? downloadCoursesPdf(school) : downloadCoursesImage(school));
    } catch (error) {
      toast.error(errorMessage(error, 'Could not download the course list. Please try again.'));
    } finally {
      setBusy('');
    }
  };

  return (
    <section className="gx-card course-sheet" aria-label="Download this school's courses">
      <div className="course-sheet-text">
        <strong>Share {school.name}&apos;s courses</strong>
        <span>Every course with its tuition, ready to send to a student.</span>
      </div>
      <div className="course-sheet-actions">
        <button type="button" className="agent-btn agent-btn-secondary" onClick={() => run('pdf')} disabled={Boolean(busy)}>
          {busy === 'pdf' ? <span className="spinner-sm" aria-hidden="true" /> : <Icon name="download" size={16} />}
          PDF
        </button>
        <button type="button" className="agent-btn agent-btn-secondary" onClick={() => run('image')} disabled={Boolean(busy)}>
          {busy === 'image' ? <span className="spinner-sm" aria-hidden="true" /> : <Icon name="camera" size={16} />}
          Image
        </button>
      </div>
    </section>
  );
}
