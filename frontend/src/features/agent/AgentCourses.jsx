import { useNavigate } from 'react-router-dom';
import { CourseBrowser } from '../applicant/CoursesPanel';

/**
 * Courses for partner agents: the same country, university, course browser the
 * applicants use, so both sides describe a course the same way. Choosing one
 * starts registering a student on it.
 */
export default function AgentCourses() {
  const navigate = useNavigate();
  return (
    <CourseBrowser
      applyLabel="Register a student"
      onApply={({ school, country }) =>
        navigate('/agent/students/new', { state: { destination: country, institution: school.slug } })
      }
    />
  );
}
