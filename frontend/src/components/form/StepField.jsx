import Icon from '../../lib/icons';

/**
 * A labelled form field for the step-by-step forms: an icon, the label, and
 * an inline asterisk when the field is required, all on one line.
 */
export default function StepField({ icon, label, required, htmlFor, labelId, error, hint, children }) {
  const Tag = htmlFor ? 'label' : 'span';
  return (
    <div className={`nf-field${error ? ' has-error' : ''}`}>
      <Tag className="nf-label" htmlFor={htmlFor} id={labelId}>
        {icon ? <Icon name={icon} size={16} className="nf-label-icon" /> : null}
        <span>{label}</span>
        {required ? <span className="nf-req" aria-hidden="true">*</span> : null}
      </Tag>
      {children}
      {hint && !error ? <span className="nf-hint">{hint}</span> : null}
      {error ? <span className="nf-error">{String(error)}</span> : null}
    </div>
  );
}
