import "./PageHeader.css";

export function PageHeader({ title, action }) {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      {action}
    </div>
  );
}
