export default function OpenTrainLogo() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 120 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="logo"
    >

      {/* Top Node */}
      <circle cx="60" cy="10" r="4" fill="var(--accent)" />

      {/* Level 1 */}
      <circle cx="40" cy="25" r="4" fill="var(--accent)" />
      <circle cx="60" cy="25" r="4" fill="var(--accent)" />
      <circle cx="80" cy="25" r="4" fill="var(--accent)" />

      {/* Level 2 */}
      <circle cx="30" cy="45" r="4" fill="var(--accent)" />
      <circle cx="50" cy="45" r="4" fill="var(--accent)" />
      <circle cx="70" cy="45" r="4" fill="var(--accent)" />
      <circle cx="90" cy="45" r="4" fill="var(--accent)" />

      {/* Level 3 */}
      <circle cx="25" cy="65" r="4" fill="var(--accent)" />
      <circle cx="35" cy="65" r="4" fill="var(--accent)" />
      <circle cx="45" cy="65" r="4" fill="var(--accent)" />
      <circle cx="55" cy="65" r="4" fill="var(--accent)" />
      <circle cx="65" cy="65" r="4" fill="var(--accent)" />
      <circle cx="75" cy="65" r="4" fill="var(--accent)" />
      <circle cx="85" cy="65" r="4" fill="var(--accent)" />
      <circle cx="95" cy="65" r="4" fill="var(--accent)" />

      {/* Connections */}
      <line x1="60" y1="10" x2="40" y2="25" stroke="var(--accent)" strokeWidth="2" />
      <line x1="60" y1="10" x2="60" y2="25" stroke="var(--accent)" strokeWidth="2" />
      <line x1="60" y1="10" x2="80" y2="25" stroke="var(--accent)" strokeWidth="2" />

      <line x1="40" y1="25" x2="30" y2="45" stroke="var(--accent)" strokeWidth="2" />
      <line x1="40" y1="25" x2="50" y2="45" stroke="var(--accent)" strokeWidth="2" />

      <line x1="60" y1="25" x2="50" y2="45" stroke="var(--accent)" strokeWidth="2" />
      <line x1="60" y1="25" x2="70" y2="45" stroke="var(--accent)" strokeWidth="2" />

      <line x1="80" y1="25" x2="70" y2="45" stroke="var(--accent)" strokeWidth="2" />
      <line x1="80" y1="25" x2="90" y2="45" stroke="var(--accent)" strokeWidth="2" />

    </svg>
  );
}