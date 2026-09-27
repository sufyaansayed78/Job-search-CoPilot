import "./FitScore.css";

const VERDICT_LABELS = {
  strong_fit: "Strong fit",
  stretch: "Stretch",
  skip: "Skip",
};

export function FitScore({ status, score, recommendation, size = "md" }) {
  if (status !== "done") {
    const isPending = status === "pending";
    return (
      <div className={`fit-score fit-score--${size} fit-score--pending`}>
        <span className={`fit-score__num mono ${isPending ? "pulse" : ""}`}>--</span>
        <span className="fit-score__label">{isPending ? "Analyzing" : "Not analyzed"}</span>
      </div>
    );
  }

  return (
    <div className={`fit-score fit-score--${size} fit-score--${recommendation}`}>
      <span className="fit-score__num mono">{Math.round(score)}</span>
      <span className="fit-score__label">{VERDICT_LABELS[recommendation] || recommendation}</span>
    </div>
  );
}

export function VerdictBar({ status, recommendation }) {
  const cls = status === "done" ? recommendation : status === "pending" ? "pending" : "none";
  return <div className={`verdict-bar verdict-bar--${cls}`} />;
}
