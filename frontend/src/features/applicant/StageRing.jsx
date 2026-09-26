/**
 * One ring whose segments are the real application stages, not a percentage.
 * A visa application is not "40% complete" — it is at a named stage out of a
 * known set, and the ring says which.
 */
export default function StageRing({ stages, index }) {
  const radius = 56;
  const circumference = 2 * Math.PI * radius;
  const segment = circumference / stages.length - 6;

  return (
    <svg
      className="ring"
      viewBox="0 0 132 132"
      role="img"
      aria-label={`Stage ${index + 1} of ${stages.length}`}
    >
      {stages.map((stage, position) => {
        const offset = -(position * circumference) / stages.length;
        let stroke = 'var(--g-line-strong)';
        let opacity = 1;
        if (stage.status === 'Completed') {
          stroke = 'var(--g-accent)';
        } else if (stage.status === 'In Progress') {
          stroke = 'var(--g-accent)';
          opacity = 0.45;
        }
        return (
          <circle
            key={stage.name}
            cx="66"
            cy="66"
            r={radius}
            fill="none"
            stroke={stroke}
            strokeOpacity={opacity}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${segment.toFixed(2)} ${circumference.toFixed(2)}`}
            strokeDashoffset={offset.toFixed(2)}
            transform="rotate(-90 66 66)"
          />
        );
      })}
      <text
        x="66"
        y="66"
        textAnchor="middle"
        fontSize="30"
        fontWeight="600"
        letterSpacing="-1"
        fill="var(--g-ink)"
      >
        {index + 1}
      </text>
      <text x="66" y="85" textAnchor="middle" fontSize="12" fontWeight="500" fill="var(--g-ink-3)">
        of {stages.length}
      </text>
    </svg>
  );
}
