import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';

/**
 * Shown once the fee settles. The password is emailed rather than printed here,
 * so this only confirms the reference and where to look for the sign-in details.
 */
export default function ProvisioningModal({ open, details, onContinue }) {
  if (!details) return null;

  return (
    <Modal
      open={open}
      dismissable={false}
      title="Application submitted"
      labelledBy="provisioning-title"
      size={540}
      footer={
        <button type="button" className="btn btn-primary btn-lg btn-block" onClick={onContinue}>
          Open my dashboard
          <Icon name="arrowRight" size={16} strokeWidth={2} />
        </button>
      }
    >
      <p style={{ marginBottom: 16 }}>
        Your file is with the admissions desk, <strong>{details.fullName}</strong>.
      </p>

      <div className="credential-box">
        <div className="cred-row">
          <span className="cred-label">Reference</span>
          <span className="cred-val">{details.reference}</span>
        </div>
        <div className="cred-row">
          <span className="cred-label">Email</span>
          <span className="cred-val">{details.email}</span>
        </div>
      </div>

      <div className="callout callout-success" style={{ marginBottom: 0 }}>
        <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
        <div className="callout-content" style={{ fontSize: '0.8125rem' }}>
          {details.accountCreated
            ? 'Your password has been emailed to you. Check your inbox to sign in, and change it from your profile whenever you like.'
            : 'Track every stage of your application from your dashboard.'}
        </div>
      </div>
    </Modal>
  );
}
