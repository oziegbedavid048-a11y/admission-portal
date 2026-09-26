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
          <span className="cred-label">Email / Login ID</span>
          <span className="cred-val">{details.email}</span>
        </div>
      </div>

      {details.isCustomCourse ? (
        <div className="callout callout-info" style={{ marginTop: 14, marginBottom: 14 }}>
          <Icon name="cap" size={20} className="callout-icon" strokeWidth={2} />
          <div className="callout-content" style={{ fontSize: '0.8125rem' }}>
            <strong>Custom Course Request Received:</strong> Our global admissions team will review your chosen course (<strong>{details.customCourseName}</strong>) in <strong>{details.destinationCountry}</strong> and reach out to you directly to guide you through university options.
          </div>
        </div>
      ) : null}

      <div className="callout callout-success" style={{ marginBottom: 0 }}>
        <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
        <div className="callout-content" style={{ fontSize: '0.8125rem' }}>
          {details.accountCreated
            ? 'Your account has been created and your password has also been sent to your email. You can change your password anytime from your profile.'
            : 'Track every stage of your application from your student dashboard.'}
        </div>
      </div>
    </Modal>
  );
}
