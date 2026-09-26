import { useEffect, useMemo, useState } from 'react';
import { ArcElement, Chart as ChartJS, Legend, Tooltip } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import { chartTone } from './Chart';

ChartJS.register(ArcElement, Tooltip, Legend);

/**
 * The one ring chart in the product.
 *
 * Both the applicant's verification ring and the agent's pipeline ring used to
 * carry their own Chart.js setup and their own hex colours, which is how one
 * ended up blue, amber and emerald while the other was blue, amber and purple.
 * There is one engine here and one palette, and a caller never names a colour:
 * it names what a segment *means* and the tone is looked up.
 *
 * The two callers still own their legends, because they list different things:
 * four fixed checkpoints that are either cleared or not, against a funnel whose
 * stages hold a changing number of students. Only the drawing is shared.
 */

/**
 * Semantic tone to design token.
 *
 * `step1` to `step4` are the ordinal ramp, for a funnel where the order of the
 * stages is the point; step 4 is the brand green, so the far end of a funnel is
 * the brand. `done`, `active`, `pending` and `bad` are for a status where the
 * order means nothing.
 */
const TONE_TOKENS = {
  step1: ['--g-chart-1', '#7fbe9c'],
  step2: ['--g-chart-2', '#4e9f79'],
  step3: ['--g-chart-3', '#227152'],
  step4: ['--g-chart-4', '#0b5c43'],
  done: ['--g-chart-4', '#0b5c43'],
  active: ['--g-chart-2', '#4e9f79'],
  pending: ['--g-chart-muted', '#948a78'],
  bad: ['--g-neg', '#a32020'],
  surface: ['--g-surface', '#ffffff'],
  ink: ['--g-ink', '#08211b'],
  ink2: ['--g-ink-2', '#54665f'],
  line: ['--g-line', '#e6dfd1'],
};

function readTones() {
  return Object.fromEntries(
    Object.entries(TONE_TOKENS).map(([name, [token, fallback]]) => [
      name,
      chartTone(token, fallback),
    ]),
  );
}

/**
 * Resolved colours for a set of segments, kept in step with the theme.
 *
 * Canvas cannot read a CSS custom property, so the tokens have to be resolved
 * against the document. Re-resolved when `data-theme` changes, which is what
 * keeps the ring and its legend in the same palette in dark appearance.
 */
export function useSegmentTones(segments) {
  const [tones, setTones] = useState(readTones);

  useEffect(() => {
    const observer = new MutationObserver(() => setTones(readTones()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    return () => observer.disconnect();
  }, []);

  const colors = useMemo(
    () => segments.map((segment) => tones[segment.tone] || tones.pending),
    [segments, tones],
  );

  return { tones, colors };
}

export default function StatusRing({
  segments,
  weights = 'equal',
  cutout = '72%',
  onHoverChange,
  tooltipLabel,
  ariaLabel,
  children,
}) {
  const { tones, colors } = useSegmentTones(segments);

  const data = {
    labels: segments.map((segment) => segment.label),
    datasets: [
      {
        // Equal weights turn the ring into four quarters that each stand for one
        // checkpoint, rather than a share of anything.
        data: segments.map((segment) => (weights === 'equal' ? 1 : segment.value || 0)),
        backgroundColor: colors,
        borderColor: tones.surface,
        borderWidth: 3,
        spacing: 2,
        borderRadius: 5,
        hoverOffset: 7,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout,
    animation: { duration: 400, easing: 'easeOutQuart' },
    onHover: (event, elements) => {
      onHoverChange?.(elements?.length ? elements[0].index : null);
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: tones.ink,
        titleColor: tones.surface,
        bodyColor: tones.surface,
        borderColor: tones.line,
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        boxPadding: 4,
        usePointStyle: true,
        callbacks: {
          label: (context) => {
            const segment = segments[context.dataIndex];
            if (tooltipLabel) return ` ${tooltipLabel(segment, context.parsed)}`;
            return ` ${segment.label}: ${segment.statusLabel || context.parsed}`;
          },
        },
      },
    },
  };

  return (
    <>
      <Doughnut data={data} options={options} aria-label={ariaLabel} />
      {children}
    </>
  );
}
