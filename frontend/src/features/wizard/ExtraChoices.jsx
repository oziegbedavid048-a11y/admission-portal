import { useMemo } from 'react';
import { useInstitutions } from '../../hooks/useCatalog';
import ProgramPicker from './ProgramPicker';

/**
 * The 2nd and 3rd choice schools, under the 1st choice's application fee.
 *
 * One fee covers two schools; a 3rd adds ₦100,000. Each choice is a partner
 * school (any destination) with up to two of its courses, and becomes its own
 * application. Used by the applicant's application and the agent's Register a
 * student.
 *
 * `choices` is [{ country, institution, programs }]; `taken` lists the school
 * slugs already used (the 1st choice, and schools already applied to) so they
 * cannot be picked twice.
 */

export const EXTRA_SCHOOL_FEE_NGN = 100000;
export const MAX_EXTRA_CHOICES = 2;

const LABELS = [
  { title: '2nd choice school', note: 'Included in your application fee' },
  { title: '3rd choice school', note: 'Adds ₦100,000 to the application fee' },
];

function ChoiceRow({ index, choice, destinations, taken, onChange, onRemove, onNotify, error }) {
  const { institutions, loading } = useInstitutions(choice.country);
  // Schools already used elsewhere on this application are not offered.
  const available = useMemo(
    () => (institutions || []).filter((item) => item.slug === choice.institution || !taken.includes(item.slug)),
    [institutions, taken, choice.institution],
  );
  const label = LABELS[index];

  return (
    <div className={`nf-choice${error ? ' has-error' : ''}`}>
      <div className="nf-choice-head">
        <div>
          <strong className="nf-choice-title">{label.title}</strong>
          <span className="nf-choice-note">{label.note}</span>
        </div>
        <button type="button" className="nf-link-btn" onClick={onRemove}>
          Remove
        </button>
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor={`choice-${index}-country`}>
          Country <span className="req">*</span>
        </label>
        <select
          id={`choice-${index}-country`}
          className="form-control"
          value={choice.country || ''}
          onChange={(event) => onChange({ country: event.target.value, institution: '', programs: [] })}
        >
          <option value="" />
          {destinations.map((item) => (
            <option key={item.name} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      {choice.country ? (
        <ProgramPicker
          institutions={available}
          loading={loading}
          countryName={choice.country}
          allowCustom={false}
          idPrefix={`choice-${index}`}
          selection={{ institution: choice.institution, level: null, programs: choice.programs || [], is_custom_course: false }}
          onChange={(next) =>
            onChange({
              ...choice,
              institution: next.institution || '',
              // Kept for the review step, which shows the school by name.
              institutionName: available.find((item) => item.slug === next.institution)?.name || '',
              programs: next.programs || [],
            })
          }
          onNotify={onNotify}
        />
      ) : null}
      {error ? <p className="nf-error">{error}</p> : null}
    </div>
  );
}

export default function ExtraChoices({ choices, destinations, taken = [], onChange, onNotify, errors = [] }) {
  const usedSlugs = (except) => [
    ...taken,
    ...choices.filter((_, position) => position !== except).map((item) => item.institution).filter(Boolean),
  ];

  const setChoice = (index, value) => onChange(choices.map((item, position) => (position === index ? value : item)));
  const removeChoice = (index) => onChange(choices.filter((_, position) => position !== index));
  const addChoice = () => onChange([...choices, { country: '', institution: '', programs: [] }]);

  return (
    <div className="nf-choices">
      {choices.map((choice, index) => (
        <ChoiceRow
          key={index}
          index={index}
          choice={choice}
          destinations={destinations}
          taken={usedSlugs(index)}
          onChange={(value) => setChoice(index, value)}
          onRemove={() => removeChoice(index)}
          onNotify={onNotify}
          error={errors[index]}
        />
      ))}
      {choices.length < MAX_EXTRA_CHOICES ? (
        <button type="button" className="agent-btn agent-btn-secondary nf-choice-add" onClick={addChoice}>
          {choices.length === 0
            ? '+ Add a 2nd choice school (included in the fee)'
            : '+ Add a 3rd choice school (+₦100,000)'}
        </button>
      ) : null}
    </div>
  );
}

/** Problems with the extra choices, one message per choice (or empty). */
export function choiceErrors(choices) {
  const seen = new Set();
  return choices.map((choice, index) => {
    const label = index === 0 ? '2nd' : '3rd';
    if (!choice.country) return `Choose a country for your ${label} choice.`;
    if (!choice.institution) return `Choose a school for your ${label} choice.`;
    if (!choice.programs?.length) return `Choose at least one course for your ${label} choice.`;
    if (seen.has(choice.institution)) return 'Choose a different school for each choice.';
    seen.add(choice.institution);
    return '';
  });
}

/** What the server is sent for the extra choices. */
export function choicesPayload(choices) {
  return choices.map((choice) => ({
    institution: choice.institution,
    program_ids: (choice.programs || []).map((program) => program.id),
  }));
}
