// Фирменный знак MedServicePrice (логотип /logo.png).
// На тёмном фоне (tone="paper") логотип выводится в монохроме (белый).

export function BrandMark({
  className = "",
  tone = "ink",
}: {
  className?: string;
  showWordmark?: boolean;
  tone?: "ink" | "paper";
}) {
  return (
    <span className={`inline-flex items-center ${className}`}>
      <img
        src="/logo.png"
        alt="MedServicePrice"
        draggable={false}
        className={`h-7 w-auto select-none ${
          tone === "paper" ? "brightness-0 invert" : ""
        }`}
      />
    </span>
  );
}

export default BrandMark;
