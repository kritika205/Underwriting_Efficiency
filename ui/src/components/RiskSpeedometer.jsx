export default function RiskSpeedometer({ score = 0 }) {
 
  const size = 320;
  const radius = 120;
  const stroke = 18;
  const center = size / 2;
  const clampedScore = Math.min(100, Math.max(0, score));
 
  const angle = -180 + (clampedScore / 100) * 180;
  const rad = (angle * Math.PI) / 180;
 
  const needleX = center + radius * Math.cos(rad);
  const needleY = center + radius * Math.sin(rad);
 
  const polar = (cx, cy, r, a) => {
    const rad = (a * Math.PI) / 180;
    return {
      x: cx + r * Math.cos(rad),
      y: cy + r * Math.sin(rad),
    };
  };
 
  const arc = (start, end) => {
    const s = polar(center, center, radius, start);
    const e = polar(center, center, radius, end);
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 0 1 ${e.x} ${e.y}`;
  };
 
  const label =
    clampedScore >= 80 ? "CRITICAL" :
    clampedScore >= 60 ? "HIGH" :
    clampedScore >= 40 ? "MEDIUM" : "LOW";
 
  return (
<div style={{ width: size, textAlign: "center" }}>
<svg width={size} height={center + 20}>
 
        {/* Green */}
<path d={arc(-180, -120)} stroke="#22c55e" strokeWidth={stroke} fill="none" />
        {/* Yellow */}
<path d={arc(-120, -60)} stroke="#facc15" strokeWidth={stroke} fill="none" />
        {/* Orange */}
<path d={arc(-60, -20)} stroke="#fb923c" strokeWidth={stroke} fill="none" />
        {/* Red */}
<path d={arc(-20, 0)} stroke="#ef4444" strokeWidth={stroke} fill="none" />
 
        {/* Needle */}
<line
          x1={center}
          y1={center}
          x2={needleX}
          y2={needleY}
          stroke="#111"
          strokeWidth="4"
          style={{ transition: "all 0.4s ease-out" }}
        />
<circle cx={center} cy={center} r="7" fill="#111" />
 
        {/* Scale Labels */}
<text x="20" y={center + 10} fontSize="12">0</text>
<text x={center - 8} y="30" fontSize="12">50</text>
<text x={size - 30} y={center + 10} fontSize="12">100</text>
</svg>
 
      <div style={{ fontSize: 36, fontWeight: 700 }}>{clampedScore}</div>
<div style={{ fontSize: 14, fontWeight: 600, color: "#dc2626" }}>
        {label} RISK
</div>
</div>
  );
}