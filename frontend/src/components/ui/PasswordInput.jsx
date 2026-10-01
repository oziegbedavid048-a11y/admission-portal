import { useState } from 'react';

/**
 * A password input with a Show / Hide button, for sign-in forms, so a person
 * can check what they typed. Takes the same props as an <input>; the input
 * keeps whatever `className` the form around it uses.
 *
 * For choosing a new password, PasswordField adds the strength checks too.
 */
export default function PasswordInput({ id, className = 'gx-input', ...props }) {
  const [shown, setShown] = useState(false);

  return (
    <div className="gx-password-wrap">
      <input id={id} type={shown ? 'text' : 'password'} className={className} {...props} />
      <button
        type="button"
        className="gx-btn gx-btn-ghost gx-btn-sm gx-password-toggle"
        onClick={() => setShown((current) => !current)}
        aria-pressed={shown}
        aria-controls={id}
        aria-label={shown ? 'Hide password' : 'Show password'}
      >
        {shown ? 'Hide' : 'Show'}
      </button>
    </div>
  );
}
