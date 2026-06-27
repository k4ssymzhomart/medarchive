// Лента, реагирующая на скорость скролла: ускоряется при прокрутке и меняет
// направление по знаку (landing-page-craft.md). Базовая скорость медленная.
// Под reduced-motion — статичный ряд.

import { useRef } from "react";
import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
  useReducedMotion,
} from "framer-motion";

const ITEMS = [
  "Единый справочник",
  "История цен",
  "Код тарификатора",
  "OCR для сканов",
  "Детектор аномалий",
  "Очередь верификации",
  "Происхождение каждой цифры",
];

const wrap = (min: number, max: number, v: number) => {
  const range = max - min;
  return ((((v - min) % range) + range) % range) + min;
};

function Row() {
  return (
    <div className="flex shrink-0 items-center">
      {ITEMS.map((it) => (
        <span key={it} className="flex items-center">
          <span className="px-8 text-2xl font-medium tracking-tight text-ink md:text-3xl">{it}</span>
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        </span>
      ))}
    </div>
  );
}

export function Marquee() {
  const reduce = useReducedMotion();
  const baseX = useMotionValue(0);
  const directionFactor = useRef(1);
  const { scrollY } = useScroll();
  const scrollVelocity = useVelocity(scrollY);
  const smoothVelocity = useSpring(scrollVelocity, { damping: 50, stiffness: 400 });
  const velocityFactor = useTransform(smoothVelocity, [0, 1000], [0, 4], { clamp: false });
  const x = useTransform(baseX, (v) => `${wrap(-25, 0, v)}%`);

  useAnimationFrame((_t, delta) => {
    let moveBy = directionFactor.current * -6 * (delta / 1000);
    const vf = velocityFactor.get();
    if (vf < 0) directionFactor.current = -1;
    else if (vf > 0) directionFactor.current = 1;
    moveBy += directionFactor.current * moveBy * vf;
    baseX.set(baseX.get() + moveBy);
  });

  if (reduce) {
    return (
      <section className="overflow-hidden border-y border-line bg-paper py-10">
        <div className="flex justify-center">
          <Row />
        </div>
      </section>
    );
  }

  return (
    <section className="overflow-hidden border-y border-line bg-paper py-10">
      <motion.div className="flex w-max flex-nowrap" style={{ x }}>
        <Row />
        <Row />
        <Row />
        <Row />
      </motion.div>
    </section>
  );
}

export default Marquee;
