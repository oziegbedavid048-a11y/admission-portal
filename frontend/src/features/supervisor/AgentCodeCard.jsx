import { useState } from 'react';
import Icon from '../../lib/icons';
import { useToast } from '../../context/ToastContext';

/**
 * The code that builds the team.
 *
 * It is the single most useful thing on a Sales Manager's screen, because an
 * agent cannot join without it, so it gets its own card with one job: be read
 * out or copied correctly.
 */
export default function AgentCodeCard({ code, agentCount }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success('Agent code copied.');
      window.setTimeout(() => setCopied(false), 2400);
    } catch {
      toast.warning('Copying is blocked in this browser. Select the code and copy it by hand.');
    }
  };

  return (
    <section className="agent-card code-card">
      <div className="code-card-body">
        <div>
          <div className="code-card-label">Your agent code</div>
          <div className="code-card-value">{code}</div>
          <p className="code-card-note">
            Give this to an agent and they enter it when they register. Every student
            they file then appears here.
          </p>
        </div>

        <div className="code-card-side">
          <button type="button" className="agent-btn agent-btn-primary" onClick={copy}>
            <Icon name={copied ? 'check' : 'copy'} size={16} strokeWidth={2.2} />
            {copied ? 'Copied' : 'Copy code'}
          </button>
          <span className="code-card-count">
            {agentCount} agent{agentCount === 1 ? '' : 's'} joined
          </span>
        </div>
      </div>
    </section>
  );
}
