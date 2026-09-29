import { useState, useEffect } from 'react';
import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { applications } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { compressImageFile } from '../../lib/compress';

const QUALIFICATIONS = [
  'SSCE / High School',
  'OND',
  'HND',
  "Bachelor's Degree",
  "Master's Degree",
];

export default function CorrectionBottomSheetModal({
  open,
  onClose,
  application,
  onSuccess,
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    address: '',
    origin_country: '',
    destination_country: '',
    qualification: '',
    previous_schools: '',
    year_graduated: '',
    grade_gpa: '',
    institution: '',
    course: '',
    reason: '',
    evidence: null,
  });

  // Populate form with current application details whenever modal opens
  useEffect(() => {
    if (application && open) {
      setForm({
        full_name: application.full_name || '',
        email: application.email || '',
        phone: application.phone || '',
        address: application.address || '',
        origin_country: application.origin_country || '',
        destination_country: application.destination_country || '',
        qualification: application.qualification || '',
        previous_schools: application.previous_schools || '',
        year_graduated: application.year_graduated ? String(application.year_graduated) : '',
        grade_gpa: application.grade_gpa || '',
        institution: application.institution?.name || '',
        course: application.programs?.[0]?.name || '',
        reason: '',
        evidence: null,
      });
    }
  }, [application, open]);

  if (!open) return null;

  const handleEvidenceChange = async (e) => {
    const raw = e.target.files?.[0] || null;
    if (raw) {
      const processed = await compressImageFile(raw);
      setForm((prev) => ({ ...prev, evidence: processed }));
    } else {
      setForm((prev) => ({ ...prev, evidence: null }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Detect all modified fields
    const changes = [];
    if (form.full_name.trim() !== (application?.full_name || '').trim()) {
      changes.push({
        field: 'Legal name',
        current_value: application?.full_name || '',
        corrected_value: form.full_name.trim(),
      });
    }
    if (form.email.trim() !== (application?.email || '').trim()) {
      changes.push({
        field: 'Email',
        current_value: application?.email || '',
        corrected_value: form.email.trim(),
      });
    }
    if (form.phone.trim() !== (application?.phone || '').trim()) {
      changes.push({
        field: 'Phone',
        current_value: application?.phone || '',
        corrected_value: form.phone.trim(),
      });
    }
    if (form.address.trim() !== (application?.address || '').trim()) {
      changes.push({
        field: 'Address',
        current_value: application?.address || '',
        corrected_value: form.address.trim(),
      });
    }
    if (form.origin_country.trim() !== (application?.origin_country || '').trim()) {
      changes.push({
        field: 'Country of origin',
        current_value: application?.origin_country || '',
        corrected_value: form.origin_country.trim(),
      });
    }
    if (form.destination_country.trim() !== (application?.destination_country || '').trim()) {
      changes.push({
        field: 'Destination country',
        current_value: application?.destination_country || '',
        corrected_value: form.destination_country.trim(),
      });
    }
    if (form.qualification !== (application?.qualification || '')) {
      changes.push({
        field: 'Qualification',
        current_value: application?.qualification || '',
        corrected_value: form.qualification,
      });
    }
    if (form.previous_schools.trim() !== (application?.previous_schools || '').trim()) {
      changes.push({
        field: 'Previous schools',
        current_value: application?.previous_schools || '',
        corrected_value: form.previous_schools.trim(),
      });
    }
    if (String(form.year_graduated || '').trim() !== String(application?.year_graduated || '').trim()) {
      changes.push({
        field: 'Year graduated',
        current_value: String(application?.year_graduated || ''),
        corrected_value: String(form.year_graduated).trim(),
      });
    }
    if (form.grade_gpa.trim() !== (application?.grade_gpa || '').trim()) {
      changes.push({
        field: 'Grade or GPA',
        current_value: application?.grade_gpa || '',
        corrected_value: form.grade_gpa.trim(),
      });
    }
    if (form.institution.trim() !== (application?.institution?.name || '').trim()) {
      changes.push({
        field: 'Institution',
        current_value: application?.institution?.name || '',
        corrected_value: form.institution.trim(),
      });
    }
    if (form.course.trim() !== (application?.programs?.[0]?.name || '').trim()) {
      changes.push({
        field: 'Course',
        current_value: application?.programs?.[0]?.name || '',
        corrected_value: form.course.trim(),
      });
    }

    if (changes.length === 0 && !form.reason.trim()) {
      toast.warning('Please modify at least one field or provide a correction explanation.');
      return;
    }

    const defaultReason = form.reason.trim() || 'Applicant requested updates to their application details.';

    setBusy(true);
    try {
      if (changes.length > 0) {
        // Submit correction request for each changed field
        for (const item of changes) {
          await applications.requestCorrection(application.reference, {
            field: item.field,
            current_value: item.current_value,
            corrected_value: item.corrected_value,
            reason: defaultReason,
            evidence: form.evidence,
          });
        }
      } else {
        // General correction request
        await applications.requestCorrection(application.reference, {
          field: 'General Profile Update',
          current_value: 'N/A',
          corrected_value: defaultReason,
          reason: defaultReason,
          evidence: form.evidence,
        });
      }

      toast.success('Your correction request has been submitted for admissions review.');
      if (onSuccess) await onSuccess();
      onClose();
    } catch (error) {
      toast.error(errorMessage(error, 'Could not submit correction request. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Request a correction"
      subtitle="Change any detail below. Everything you send goes to the admissions desk for verification and approval."
      labelledBy="correction-sheet-title"
      size={640}
      footer={
        <div className="corr-modal-footer">
          <button
            type="button"
            className="g-btn g-btn-plain"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="correction-form"
            className="g-btn g-btn-primary"
            disabled={busy}
          >
            <Icon name="arrowRight" size={16} strokeWidth={2.2} />
            <span>{busy ? 'Submitting...' : 'Submit correction request'}</span>
          </button>
        </div>
      }
    >
      <form id="correction-form" onSubmit={handleSubmit} className="corr-form-body">
        {/* Section 1: Personal Information */}
        <div className="corr-section">
          <div className="corr-sec-head">
            <Icon name="user" size={16} />
            <h4>Personal information</h4>
          </div>
          <div className="corr-form-grid">
            <div className="corr-field">
              <label htmlFor="corr_full_name">Legal full name</label>
              <input
                type="text"
                id="corr_full_name"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Full Name as on Passport"
                required
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_email">Email address</label>
              <input
                type="email"
                id="corr_email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
                required
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_phone">Phone number</label>
              <input
                type="tel"
                id="corr_phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="+234..."
                required
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_address">Residential address</label>
              <input
                type="text"
                id="corr_address"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="Street, City, State"
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_origin">Country of Origin</label>
              <input
                type="text"
                id="corr_origin"
                value={form.origin_country}
                onChange={(e) => setForm({ ...form, origin_country: e.target.value })}
                placeholder="Country of Origin"
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_destination">Destination country</label>
              <input
                type="text"
                id="corr_destination"
                value={form.destination_country}
                onChange={(e) => setForm({ ...form, destination_country: e.target.value })}
                placeholder="Target Destination Country"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Academic Background */}
        <div className="corr-section">
          <div className="corr-sec-head">
            <Icon name="cap" size={16} />
            <h4>Academic background</h4>
          </div>
          <div className="corr-form-grid">
            <div className="corr-field">
              <label htmlFor="corr_qualification">Highest qualification</label>
              <select
                id="corr_qualification"
                value={form.qualification}
                onChange={(e) => setForm({ ...form, qualification: e.target.value })}
              >
                <option value="">Select qualification</option>
                {QUALIFICATIONS.map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>

            <div className="corr-field">
              <label htmlFor="corr_school">Previous School / Institution</label>
              <input
                type="text"
                id="corr_school"
                value={form.previous_schools}
                onChange={(e) => setForm({ ...form, previous_schools: e.target.value })}
                placeholder="High School or College Name"
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_year">Year graduated</label>
              <input
                type="number"
                id="corr_year"
                min="1960"
                max="2035"
                value={form.year_graduated}
                onChange={(e) => setForm({ ...form, year_graduated: e.target.value })}
                placeholder="e.g. 2023"
              />
            </div>

            <div className="corr-field">
              <label htmlFor="corr_gpa">Grade or GPA</label>
              <input
                type="text"
                id="corr_gpa"
                value={form.grade_gpa}
                onChange={(e) => setForm({ ...form, grade_gpa: e.target.value })}
                placeholder="e.g. 3.8 / 4.0 or Upper Credit"
              />
            </div>
          </div>
        </div>

        {/* Section 3: University & Programme Selection */}
        <div className="corr-section">
          <div className="corr-sec-head">
            <Icon name="document" size={16} />
            <h4>University & course selection</h4>
          </div>
          <div className="corr-form-grid">
            <div className="corr-field corr-field-full">
              <label htmlFor="corr_institution">Selected Institution / University</label>
              <input
                type="text"
                id="corr_institution"
                value={form.institution}
                onChange={(e) => setForm({ ...form, institution: e.target.value })}
                placeholder="Name of chosen university"
              />
            </div>

            <div className="corr-field corr-field-full">
              <label htmlFor="corr_course">Selected Course / Programme</label>
              <input
                type="text"
                id="corr_course"
                value={form.course}
                onChange={(e) => setForm({ ...form, course: e.target.value })}
                placeholder="Degree Major / Programme Name"
              />
            </div>
          </div>
        </div>

        {/* Section 4: Correction Reason & Supporting Evidence */}
        <div className="corr-section">
          <div className="corr-sec-head">
            <Icon name="fileText" size={16} />
            <h4>Reason & supporting evidence</h4>
          </div>

          <div className="corr-form-grid">
            <div className="corr-field corr-field-full">
              <label htmlFor="corr_reason">Reason for Correction Request *</label>
              <textarea
                id="corr_reason"
                rows={3}
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="Explain what was changed and why (e.g., corrected spelling of legal surname, updated new address, modified course choice)..."
                required
              />
            </div>

            <div className="corr-field corr-field-full">
              <label htmlFor="corr_evidence">Optional Supporting Document (PDF / Image)</label>
              <input
                type="file"
                id="corr_evidence"
                accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif"
                onChange={handleEvidenceChange}
              />
              <span className="corr-field-hint">
                Attach official evidence if you are requesting changes to legal name, birth date, or credentials.
              </span>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
