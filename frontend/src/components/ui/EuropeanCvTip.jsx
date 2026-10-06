/**
 * A short, optional suggestion under the CV upload: a European-format CV is
 * what universities in Europe are used to reading, and can help an
 * application. Advice only; any CV is accepted.
 */
export const EUROPEAN_CV_URL = 'https://quotahire.org/european-cv';

export default function EuropeanCvTip({ forStudent = false }) {
  return (
    <p className="nf-tip">
      Tip: a European-format CV can strengthen {forStudent ? "the student's" : 'your'} application.{' '}
      <a href={EUROPEAN_CV_URL} target="_blank" rel="noopener noreferrer">
        Create one with our European CV generator
      </a>
      .
    </p>
  );
}
