import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../../lib/icons';
import StatusRing, { useSegmentTones } from '../../components/charts/StatusRing';

/**
 * Where this agent's students currently sit.
 *
 * The four stages are a sequence, so they take the ordinal ramp: one hue, light
 * to dark, ending on the brand green at the stage that counts. Reading the ring
 * clockwise tells you which way the funnel runs, which a set of unrelated hues
 * could not.
 */
const STAGE_CONFIG = [
  { key: 'in_review', label: 'In review', tone: 'step1' },
  { key: 'admitted', label: 'Admitted', tone: 'step2' },
  { key: 'visa_in_progress', label: 'Visa stage', tone: 'step3' },
  { key: 'visa_verified', label: 'Verified', tone: 'step4' },
];

export default function PipelinePieChart({ pipeline, totalStudents = 0 }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const stages = useMemo(() => {
    return STAGE_CONFIG.map((cfg) => {
      const value = pipeline?.[cfg.key] || 0;
      return {
        ...cfg,
        value,
      };
    });
  }, [pipeline]);

  const total = useMemo(() => {
    const rawTotal = stages.reduce((acc, s) => acc + s.value, 0);
    return rawTotal > 0 ? rawTotal : totalStudents || 0;
  }, [stages, totalStudents]);

  // Legend dots resolve the same tokens the ring does, so they always agree.
  const { colors } = useSegmentTones(stages);
  const activeStage = hoveredIndex !== null ? stages[hoveredIndex] : null;

  if (total === 0) {
    return (
      <div className="pipeline-empty-state">
        <div className="pipeline-empty-ring">
          <Icon name="users" size={26} />
          <span className="pipeline-empty-zero">0</span>
        </div>
        <p className="pipeline-empty-title">No candidates in pipeline</p>
        <p className="pipeline-empty-desc">
          Register student applications to track their admission and visa progress in real time.
        </p>
        <Link to="/agent/students/new" className="agent-btn agent-btn-primary agent-btn-sm">
          <Icon name="userPlus" size={15} />
          Register first student
        </Link>
      </div>
    );
  }

  return (
    <div className="pipeline-chart-card">
      <div className="pipeline-chart-wrapper">
        <div className="pipeline-canvas-container">
          <StatusRing
            segments={stages}
            weights="value"
            onHoverChange={setHoveredIndex}
            tooltipLabel={(stage, value) =>
              `${stage.label}: ${value} ${value === 1 ? 'student' : 'students'}`
            }
            ariaLabel={`Student pipeline: ${total} ${total === 1 ? 'student' : 'students'}`}
          >
            <div className="pipeline-center-overlay" aria-hidden="true">
              <span className="pipeline-center-number">
                {activeStage ? activeStage.value : total}
              </span>
              <span className="pipeline-center-label">
                {activeStage ? activeStage.label : total === 1 ? 'Student' : 'Students'}
              </span>
            </div>
          </StatusRing>
        </div>
      </div>

      <div className="pipeline-plain-legend">
        {stages.map((stage, idx) => (
          <div
            key={stage.key}
            className={`pipeline-plain-item ${hoveredIndex === idx ? 'is-active' : ''}`}
            onMouseEnter={() => setHoveredIndex(idx)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <span
              className="pipeline-plain-dot"
              style={{ backgroundColor: colors[idx] }}
            />
            <span className="pipeline-plain-label">{stage.label}</span>
            <span className="pipeline-plain-count">{stage.value}</span>
          </div>
        ))}
      </div>

      <table className="sr-only">
        <caption>Student pipeline distribution</caption>
        <thead>
          <tr>
            <th>Stage</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((stage) => (
            <tr key={stage.key}>
              <td>{stage.label}</td>
              <td>{stage.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
