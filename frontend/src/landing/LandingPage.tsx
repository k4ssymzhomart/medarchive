// Публичный лендинг MedPartners. Скролл-история по landing-page-craft.md.
// Бит-лист: Hero (claim) -> Возможности (features) -> Проблема (tension) ->
// Конвейер (подписной момент, pinned scrub) -> лента -> Доказательства (счётчики)
// -> Заявление (пауза) -> CTA -> Футер. Lenis плавный скролл и MotionConfig только
// на лендинге, продукт /app не затронут.

import { MotionConfig } from "framer-motion";
import { SmoothScroll } from "./SmoothScroll";
import { Nav } from "./Nav";
import FloatingIconsHeroDemo from "../components/ui/floating-icons-hero-demo";
import { Features } from "../components/blocks/features-8";
import { Tension } from "./Tension";
import { Pipeline } from "./Pipeline";
import { Marquee } from "./Marquee";
import { Proof } from "./Proof";
import { Statement } from "./Statement";
import { CTA } from "./CTA";
import { SiteFooter } from "./SiteFooter";

export default function LandingPage() {
  return (
    <MotionConfig reducedMotion="user">
      <SmoothScroll>
        <div className="min-h-screen bg-paper text-ink">
          <Nav />
          <main>
            <div id="top">
              <FloatingIconsHeroDemo />
            </div>
            <div id="features">
              <Features />
            </div>
            <Tension />
            <div id="pipeline">
              <Pipeline />
            </div>
            <Marquee />
            <div id="metrics">
              <Proof />
            </div>
            <Statement />
            <CTA />
          </main>
          <SiteFooter />
        </div>
      </SmoothScroll>
    </MotionConfig>
  );
}
