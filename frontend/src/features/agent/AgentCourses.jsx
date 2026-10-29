import { useNavigate } from 'react-router-dom';
import { CourseBrowser } from '../applicant/CoursesPanel';
import CourseSheetDownload from './CourseSheetDownload';

/**
 * Courses for partner agents: the same country, university, course browser the
 * applicants use, so both sides describe a course the same way. Choosing one
 * starts registering a student on it. Each school's course list can be
 * downloaded as a PDF or an image to send to students.
 */
export default function AgentCourses() {
  const navigate = useNavigate();
  return (
    <CourseBrowser
      applyLabel="Register a student"
      schoolActions={(school) => <CourseSheetDownload school={school} />}
      onApply={({ school, country }) =>
        navigate('/agent/students/new', { state: { destination: country, institution: school.slug } })
      }
    />
  );
}
