// Публичный лендинг MedPartners. Композиция секций.
// Hero заменён на floating-icons шаблон, ниже добавлена features сетка (шаблоны).

import { Nav } from "./Nav";
import FloatingIconsHeroDemo from "../components/ui/floating-icons-hero-demo";
import { Features } from "../components/blocks/features-8";
import { LogoMarquee } from "./LogoMarquee";
import { ValueStatement } from "./ValueStatement";
import { FeatureSpotlight } from "./FeatureSpotlight";
import { Metrics } from "./Metrics";
import { FinalCTA } from "./FinalCTA";
import { Footer } from "./Footer";
import { FloatingDemo } from "./FloatingDemo";
import { CookieConsent } from "./CookieConsent";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <Nav />
      <main>
        <div id="top">
          <FloatingIconsHeroDemo />
        </div>
        <Features />
        <LogoMarquee />
        <ValueStatement />
        <FeatureSpotlight />
        <Metrics />
        <FinalCTA />
      </main>
      <Footer />
      <FloatingDemo />
      <CookieConsent />
    </div>
  );
}
