export function PlaceholderPage({
  icon,
  title,
  text,
}: {
  icon: string;
  title: string;
  text: string;
}) {
  return (
    <div className="page">
      <div className="placeholder card">
        <i>{icon}</i>
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
    </div>
  );
}
