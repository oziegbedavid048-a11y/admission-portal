import Icon from '../../lib/icons';

const STATE = {
  Completed: 'done',
  'In Progress': 'live',
  Pending: 'pending',
};

/** The vertical list of application stages, shared by the portal and the agent dossier. */
export default function StageTrack({ stages }) {
  return (
    <div className="stages">
      {stages.map((stage, index) => (
        <div className={`stage ${STATE[stage.status] || 'pending'}`} key={stage.name}>
          <span className="stage-mark">
            {stage.status === 'Completed' ? (
              <Icon name="check" size={13} strokeWidth={3} />
            ) : (
              index + 1
            )}
          </span>
          {index < stages.length - 1 ? <span className="stage-line" /> : null}
          <div className="stage-body">
            <h3>{stage.name}</h3>
            <div className="stage-when">{stage.eta || stage.status}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
