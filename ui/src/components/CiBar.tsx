interface Props {
  delta: number;
  low: number;
  high: number;
}

export function CiBar({ delta, low, high }: Props) {
  const width = 320;
  const x = (value: number) => ((value + 1) / 2) * width;
  const noise = low <= 0 && high >= 0;
  return (
    <svg className="ci-bar" viewBox={`0 0 ${width} 44`} role="img" aria-label="95% confidence interval of the difference">
      <line x1={0} x2={width} y1={22} y2={22} className="axis" />
      <line x1={x(0)} x2={x(0)} y1={6} y2={38} className="zero" />
      <rect x={x(low)} width={Math.max(x(high) - x(low), 2)} y={14} height={16} rx={3} className={noise ? 'interval noise' : 'interval'} />
      <circle cx={x(delta)} cy={22} r={5} className="point" />
      <text x={2} y={42}>−100</text>
      <text x={x(0)} y={42} textAnchor="middle">0</text>
      <text x={width - 2} y={42} textAnchor="end">+100 pp</text>
    </svg>
  );
}
