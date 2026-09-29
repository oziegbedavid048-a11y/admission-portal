import { useState } from 'react';
import Icon from '../../lib/icons';

/**
 * A new-password input with a Show button and the rules shown as they are met.
 *
 * The rules mirror the server's: at least 8 characters, not only numbers. The
 * server also refuses very common passwords and ones too close to the person's
 * name or email; those come back as field errors and appear under the input.
 */
export function passwordChecks(value) {
  return [
    { label: '8 or more characters', met: value.length >= 8 },
    { label: 'Not only numbers', met: value.length > 0 && !/^\d+$/.test(value) },
  ];
}

export default function PasswordField({
  id,
  label = 'Password',
  value,
  onChange,
  error,
  autoComplete = 'new-password',
  showChecks = true,
}) {
  const [shown, setShown] = useState(false);
  const errorId = `${id}-error`;

  return (
    <div className={`gx-field ${error ? 'has-error' : ''}`.trim()}>
      <label htmlFor={id}>{label}</label>
      <div className="gx-password-wrap">
        <input
          id={id}
          type={shown ? 'text' : 'password'}
          className="gx-input"
          autoComplete={autoComplete}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
        />
        <button
          type="button"
          className="gx-btn gx-btn-ghost gx-btn-sm gx-password-toggle"
          onClick={() => setShown((current) => !current)}
          aria-pressed={shown}
          aria-controls={id}
        >
          {shown ? 'Hide' : 'Show'}
        </button>
      </div>
      {showChecks ? (
        <ul className="gx-checks" aria-label="Password requirements">
          {passwordChecks(value).map((check) => (
            <li key={check.label} className={check.met ? 'is-met' : ''}>
              <Icon name={check.met ? 'checkCircle' : 'clock'} size={14} strokeWidth={2} />
              {check.label}
            </li>
          ))}
        </ul>
      ) : null}
      {error ? (
        <span className="gx-error" id={errorId}>
          {Array.isArray(error) ? error.join(' ') : String(error)}
        </span>
      ) : null}
    </div>
  );
}
