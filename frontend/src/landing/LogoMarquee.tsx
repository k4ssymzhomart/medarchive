// Лента источников данных. Бесконечный marquee из нейтральных плейсхолдеров
// (обезличенные клиники проекта, не чужие логотипы). При prefers-reduced-motion
// анимация выключается через CSS, лента остаётся статичной.

import {
  Activity,
  Building2,
  Cross,
  HeartPulse,
  Hospital,
  Microscope,
  Pill,
  Stethoscope,
  Syringe,
  TestTube,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ITEMS: { icon: LucideIcon; label: string }[] = [
  { icon: Hospital, label: "Клиника 01" },
  { icon: Stethoscope, label: "Клиника 02" },
  { icon: HeartPulse, label: "Клиника 03" },
  { icon: Microscope, label: "Клиника 04" },
  { icon: Building2, label: "Клиника 05" },
  { icon: Cross, label: "Клиника 06" },
  { icon: Syringe, label: "Клиника 07" },
  { icon: Pill, label: "Клиника 08" },
  { icon: TestTube, label: "Клиника 09" },
  { icon: Activity, label: "Клиника 10" },
];

const maskStyle = {
  WebkitMaskImage:
    "linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent)",
  maskImage: "linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent)",
} as const;

function Tile({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex h-16 w-48 shrink-0 items-center justify-center gap-3 rounded-card border border-line bg-paper px-5 text-muted shadow-soft">
      <Icon className="h-5 w-5" />
      <span className="text-sm font-medium tracking-tight">{label}</span>
    </div>
  );
}

export function LogoMarquee() {
  return (
    <section className="bg-paper py-16">
      <div className="mx-auto max-w-content px-6">
        <p className="eyebrow text-center text-muted">Источники данных и партнёры</p>
      </div>
      <div className="relative mt-8 overflow-hidden" style={maskStyle}>
        <div className="marquee-track gap-4 px-2">
          {[...ITEMS, ...ITEMS].map((it, i) => (
            <Tile key={i} icon={it.icon} label={it.label} />
          ))}
        </div>
      </div>
    </section>
  );
}

export default LogoMarquee;
