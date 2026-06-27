import * as React from 'react';
import {
  Activity,
  Bandage,
  Bone,
  Brain,
  ClipboardPlus,
  Cross,
  Dna,
  FlaskConical,
  HeartPulse,
  Microscope,
  Pill,
  Pipette,
  Stethoscope,
  Syringe,
  TestTubes,
  Thermometer,
  type LucideIcon,
} from 'lucide-react';
import {
  FloatingIconsHero,
  type FloatingIconsHeroProps,
} from '@/components/ui/floating-icons-hero-section';

// Никаких чужих брендов. Плавающие иконки — собственный медицинский набор
// lucide: монохромные линии под минималистичный стиль MedPartners.
// Адаптер приводит иконку lucide к сигнатуре, которую ждёт герой, и задаёт
// тонкую обводку для единого веса линий.
const med =
  (Icon: LucideIcon): React.FC<React.SVGProps<SVGSVGElement>> =>
  (props) => <Icon strokeWidth={1.5} {...props} />;

// 16 категорий медицинских услуг и инструментов на тех же позициях, что и раньше.
const demoIcons: FloatingIconsHeroProps['icons'] = [
  { id: 1, icon: med(Stethoscope), className: 'top-[10%] left-[10%]' },
  { id: 2, icon: med(Microscope), className: 'top-[20%] right-[8%]' },
  { id: 3, icon: med(FlaskConical), className: 'top-[80%] left-[10%]' },
  { id: 4, icon: med(Syringe), className: 'bottom-[10%] right-[10%]' },
  { id: 5, icon: med(HeartPulse), className: 'top-[5%] left-[30%]' },
  { id: 6, icon: med(Pill), className: 'top-[5%] right-[30%]' },
  { id: 7, icon: med(Activity), className: 'bottom-[8%] left-[25%]' },
  { id: 8, icon: med(TestTubes), className: 'top-[40%] left-[15%]' },
  { id: 9, icon: med(Thermometer), className: 'top-[75%] right-[25%]' },
  { id: 10, icon: med(Cross), className: 'top-[90%] left-[70%]' },
  { id: 11, icon: med(Dna), className: 'top-[50%] right-[5%]' },
  { id: 12, icon: med(Brain), className: 'top-[55%] left-[5%]' },
  { id: 13, icon: med(Bone), className: 'top-[5%] left-[55%]' },
  { id: 14, icon: med(Pipette), className: 'bottom-[5%] right-[45%]' },
  { id: 15, icon: med(Bandage), className: 'top-[25%] right-[20%]' },
  { id: 16, icon: med(ClipboardPlus), className: 'top-[60%] left-[30%]' },
];

export default function FloatingIconsHeroDemo() {
  return (
    <FloatingIconsHero
      title="Все прайсы клиник в одной базе"
      subtitle="Автоматически разбираем прайсы клиник партнёров, нормализуем услуги к единому справочнику и проверяем цены."
      ctaText="Запросить демо"
      ctaHref="#cta"
      icons={demoIcons}
    />
  );
}
