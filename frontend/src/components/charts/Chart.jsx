import { useEffect, useMemo, useState } from 'react';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const CHART_FONT =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

/**
 * Charts read their colours from the CSS custom properties rather than
 * hardcoding hex, so they follow the brand and the dark theme. Every chart
 * ships with a table of the same numbers underneath: that is the screen-reader
 * path, and it means no value is reachable by hover alone.
 */
/**
 * Resolve a design token to a real colour.
 *
 * Canvas has no idea what `var(--g-chart-4)` means, so a chart colour has to be
 * read off the document before it is handed over. Callers picking their own
 * slice colours use this rather than passing the token through.
 */
export function chartTone(name, fallback) {
  return readToken(name, fallback);
}

function readToken(name, fallback) {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function usePalette() {
  const [palette, setPalette] = useState(() => readPalette());

  useEffect(() => {
    const observer = new MutationObserver(() => setPalette(readPalette()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    return () => observer.disconnect();
  }, []);

  return palette;
}

function readPalette() {
  return {
    ramp: [
      readToken('--g-chart-1', '#7fbe9c'),
      readToken('--g-chart-2', '#4e9f79'),
      readToken('--g-chart-3', '#227152'),
      readToken('--g-chart-4', '#0b5c43'),
    ],
    muted: readToken('--g-chart-muted', '#948a78'),
    surface: readToken('--g-surface', '#ffffff'),
    line: readToken('--g-line', '#e6dfd1'),
    ink: readToken('--g-ink', '#08211b'),
    ink3: readToken('--g-ink-3', '#5f6f69'),
  };
}

// These series are ordered — a funnel, a verification state, earned versus
// still to earn — so they use the ordinal green ramp rather than categorical
// hues. With fewer slices than ramp steps, spread across the ends instead of
// taking adjacent steps, which would be near indistinguishable.
function spread(ramp, count) {
  if (count <= 1) return [ramp[ramp.length - 1]];
  if (count >= ramp.length) return ramp.slice(0, count);
  return Array.from({ length: count }, (_, index) =>
    ramp[Math.round((index * (ramp.length - 1)) / (count - 1))],
  );
}

function DataTable({ rows, valueLabel, format }) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  return (
    <table className="chart-table">
      <thead>
        <tr>
          <th scope="col">Item</th>
          <th scope="col">{valueLabel}</th>
          <th scope="col">Share</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">
              <span className="chart-swatch" style={{ background: row.color }} />
              {row.label}
            </th>
            <td>{format ? format(row.value) : row.value}</td>
            <td>{total ? Math.round((row.value / total) * 100) : 0}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function useRows(rows) {
  const palette = usePalette();
  return useMemo(() => {
    const tones = spread(palette.ramp, rows.length);
    return {
      palette,
      data: rows.map((row, index) => ({ ...row, color: row.color || tones[index] })),
    };
  }, [rows, palette]);
}

function baseOptions(palette, format) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 420 },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: palette.ink,
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        padding: 12,
        cornerRadius: 10,
        boxPadding: 4,
        callbacks: {
          label(context) {
            const raw = context.parsed.y !== undefined ? context.parsed.y : context.parsed;
            return ` ${format ? format(raw) : raw}`;
          },
        },
      },
    },
  };
}

function centreTextPlugin(title, value, palette) {
  return {
    id: 'centreText',
    afterDraw(chart) {
      const { ctx, chartArea } = chart;
      if (!chartArea) return;

      const x = (chartArea.left + chartArea.right) / 2;
      const y = (chartArea.top + chartArea.bottom) / 2;
      const radius = Math.min(chartArea.right - chartArea.left, chartArea.bottom - chartArea.top) / 2;

      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      // Sized off the ring so the label never outgrows the hole it sits in.
      const valueSize = Math.max(15, Math.min(30, radius * 0.34));
      ctx.font = `600 ${valueSize}px ${CHART_FONT}`;
      ctx.fillStyle = palette.ink;
      ctx.fillText(value, x, y - valueSize * 0.12);

      ctx.font = `500 ${Math.max(10, valueSize * 0.42)}px ${CHART_FONT}`;
      ctx.fillStyle = palette.ink3;
      ctx.fillText(title, x, y + valueSize * 0.72);

      ctx.restore();
    },
  };
}

/**
 * A share of a whole, drawn as a ring with the total in the middle.
 *
 * The height is responsive rather than fixed: the ring is given a range to
 * live in so it stays legible on a phone and does not swell to fill a wide
 * desktop card. Every slice is also listed in the table underneath, which is
 * the screen-reader path and means no value needs a hover to be read.
 */
export function PieChart({
  rows,
  height = 240,
  valueLabel = 'Count',
  format,
  ariaLabel,
  centreLabel,
  centreValue,
}) {
  const { palette, data } = useRows(rows);
  if (!rows.length) return null;

  const total = data.reduce((sum, row) => sum + row.value, 0);
  const plugins = centreLabel
    ? [centreTextPlugin(centreLabel, centreValue ?? (format ? format(total) : total), palette)]
    : [];

  return (
    <div>
      <div className="chart-frame chart-frame-pie" style={{ '--chart-h': `${height}px` }}>
        <Doughnut
          aria-label={ariaLabel}
          plugins={plugins}
          data={{
            labels: data.map((row) => row.label),
            datasets: [
              {
                data: data.map((row) => row.value),
                backgroundColor: data.map((row) => row.color),
                borderColor: palette.surface,
                borderWidth: 3,
                hoverOffset: 10,
                hoverBorderColor: palette.surface,
              },
            ],
          }}
          options={{
            ...baseOptions(palette, format),
            cutout: centreLabel ? '66%' : '58%',
            plugins: {
              ...baseOptions(palette, format).plugins,
              tooltip: {
                ...baseOptions(palette, format).plugins.tooltip,
                callbacks: {
                  label(context) {
                    const total =
                      context.dataset.data.reduce((sum, value) => sum + value, 0) || 1;
                    const percent = Math.round((context.parsed / total) * 100);
                    const value = format ? format(context.parsed) : context.parsed;
                    return ` ${context.label}: ${value} (${percent}%)`;
                  },
                },
              },
            },
          }}
        />
      </div>
      <DataTable rows={data} valueLabel={valueLabel} format={format} />
    </div>
  );
}

export function BarChart({ rows, height = 240, valueLabel = 'Count', format, ariaLabel }) {
  const { palette, data } = useRows(rows);
  if (!rows.length) return null;

  return (
    <div>
      <div className="chart-frame" style={{ height }}>
        <Bar
          aria-label={ariaLabel}
          data={{
            labels: data.map((row) => row.label),
            datasets: [
              {
                data: data.map((row) => row.value),
                backgroundColor: data.map((row) => row.color),
                hoverBackgroundColor: data.map((row) => row.color),
                borderRadius: 6,
                borderSkipped: false,
                maxBarThickness: 48,
              },
            ],
          }}
          options={{
            ...baseOptions(palette, format),
            scales: {
              x: {
                grid: { display: false },
                border: { color: palette.line },
                ticks: { color: palette.ink3, font: { size: 12 } },
              },
              y: {
                beginAtZero: true,
                grid: { color: palette.line, drawTicks: false },
                border: { display: false },
                ticks: { color: palette.ink3, font: { size: 12 }, precision: 0, padding: 8 },
              },
            },
          }}
        />
      </div>
      <DataTable rows={data} valueLabel={valueLabel} format={format} />
    </div>
  );
}
