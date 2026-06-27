// Reveal как семья вариантов по интенту, а не один фейд на всё (landing-page-craft.md).
// При prefers-reduced-motion показываем финальное состояние сразу, без сдвига.

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { reveals } from "../lib/motion";

type Intent = keyof typeof reveals;

export function Reveal({
  children,
  intent = "sequence",
  amount = 0.3,
  margin = "0px 0px -10% 0px",
  className = "",
}: {
  children: ReactNode;
  intent?: Intent;
  amount?: number;
  margin?: string;
  className?: string;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      variants={reveals[intent]}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount, margin: margin as never }}
    >
      {children}
    </motion.div>
  );
}

export default Reveal;
