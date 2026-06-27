// Оригинальный знак MedPartners: скруглённый тайл с акцентным градиентом и
// собственным пульс глифом. Никаких чужих логотипов.

export function BrandMark({
  className = "",
  showWordmark = true,
  tone = "ink",
}: {
  className?: string;
  showWordmark?: boolean;
  tone?: "ink" | "paper";
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="mpGrad" x1="0" y1="0" x2="30" y2="30" gradientUnits="userSpaceOnUse">
            <stop stopColor="#9A8CFF" />
            <stop offset="0.55" stopColor="#6D5EF6" />
            <stop offset="1" stopColor="#4B3FD6" />
          </linearGradient>
        </defs>
        <rect width="30" height="30" rx="9" fill="url(#mpGrad)" />
        <path
          d="M6.5 16.2h3.1l1.7-4.4 2.9 7.1 1.8-3.6h4.0"
          stroke="#FFFFFF"
          strokeWidth="2.1"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {showWordmark && (
        <span
          className={`text-lg font-semibold tracking-tight ${
            tone === "paper" ? "text-paper" : "text-ink"
          }`}
        >
          MedPartners
        </span>
      )}
    </span>
  );
}

export default BrandMark;
