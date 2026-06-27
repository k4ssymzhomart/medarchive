// Единый источник правды для моушна (см. landing-page-craft.md).
// Никаких inline магических чисел в компонентах: только эти токены.

import type { Variants } from "framer-motion";

// Кривые. ease-out для входов, ease-in для выходов (асимметрия = живость).
export const ease = {
  out: [0.16, 1, 0.3, 1] as [number, number, number, number], // expo-out, рабочая лошадка
  outSoft: [0.22, 1, 0.36, 1] as [number, number, number, number], // мягче, для крупных блоков
  inOut: [0.65, 0, 0.35, 1] as [number, number, number, number],
  in: [0.4, 0, 1, 1] as [number, number, number, number], // выходы ускоряются
};

// Пружины для интеракций (вес и инерция).
export const spring = {
  soft: { type: "spring", stiffness: 100, damping: 20, mass: 1 },
  snappy: { type: "spring", stiffness: 400, damping: 30, mass: 0.8 },
  heavy: { type: "spring", stiffness: 120, damping: 26, mass: 1.4 },
} as const;

// Одна пружина для сглаживания любого scroll-driven значения. mass низкая.
export const scrubSpring = { stiffness: 120, damping: 30, mass: 0.4 } as const;

// Семья reveal-вариантов по интенту, а не один <Reveal> на всё.
export const reveals: Record<string, Variants> = {
  // утверждение: приходит уверенно, оседает
  statement: {
    hidden: { opacity: 0, y: 12 },
    show: {
      opacity: 1,
      y: 0,
      transition: { type: "spring", stiffness: 420, damping: 32, mass: 0.9 },
    },
  },
  // свидетельство: без дрейфа, просто проявление — доверие читается как покой
  evidence: {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { duration: 0.4, ease: ease.outSoft } },
  },
  // последовательность: дети приходят по очереди (со staggerChildren на родителе)
  sequence: {
    hidden: { opacity: 0, y: 8 },
    show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: ease.out } },
  },
  // фокальный элемент: больше путь, оседает авторитетно
  lead: {
    hidden: { opacity: 0, y: 32 },
    show: {
      opacity: 1,
      y: 0,
      transition: { type: "spring", stiffness: 220, damping: 30, mass: 1 },
    },
  },
  // подчинённый: короче путь, чуть позже, без оверщута
  sub: {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 260, damping: 38 } },
  },
};

// Контейнер для оркестрованного каскада детей.
export const stagger = (staggerChildren = 0.06, delayChildren = 0.05): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren, delayChildren } },
});
