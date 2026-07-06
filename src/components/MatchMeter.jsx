// The match meter — the signature instrument. A compact 270-degree arc gauge
// with the fit score read out in mono at its center. Colour encodes the band.
export default function MatchMeter({ score = 0, size = 64, stroke = 6 }) {
  const s = Math.max(0, Math.min(100, score));
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;

  // 270-degree sweep, starting bottom-left (135deg) going clockwise.
  const START = 135;
  const SWEEP = 270;
  const circumference = 2 * Math.PI * r;
  const arcLen = (SWEEP / 360) * circumference;
  const filled = (s / 100) * arcLen;

  const color =
    s >= 70 ? "var(--petrol)" : s >= 45 ? "var(--amber)" : "var(--slate-muted)";

  // rotate so the gap sits at the bottom
  const rotation = START + 90;

  return (
    <div
      className="match-meter"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Match score ${s} of 100`}
      title={`Match ${s}/100`}
    >
      <svg width={size} height={size}>
        <g transform={`rotate(${rotation} ${cx} ${cy})`}>
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="var(--line-strong)"
            strokeWidth={stroke}
            strokeDasharray={`${arcLen} ${circumference}`}
            strokeLinecap="round"
          />
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={`${filled} ${circumference}`}
            strokeLinecap="round"
            className="meter-arc"
          />
        </g>
      </svg>
      <span className="meter-value mono" style={{ color }}>
        {s}
      </span>
    </div>
  );
}
