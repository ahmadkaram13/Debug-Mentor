const RUNGS = [
  { level: 1, label: 'Open question' },
  { level: 2, label: 'Narrowed down' },
  { level: 3, label: 'Named the smell' },
  { level: 4, label: 'Concrete nudge' },
]

export default function HintLadder({ hintLevel }) {
  return (
    <div className="ladder" aria-label="Hint escalation level">
      {RUNGS.map((rung) => (
        <div
          key={rung.level}
          className={
            'ladder-rung' +
            (rung.level === hintLevel ? ' active' : '') +
            (rung.level < hintLevel ? ' filled' : '')
          }
        >
          <span className="ladder-dot" />
          <span className="ladder-rung-label">{rung.label}</span>
        </div>
      ))}
    </div>
  )
}
