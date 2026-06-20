export function RiskBadge({ level }: { level: string }) {
  return <span className={`risk-badge risk-${level}`}>{level}</span>
}
