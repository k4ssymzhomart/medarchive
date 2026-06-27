// Публичный лендинг MedPartners. Композиция секций из ТЗ Фазы 0.1.

import { Nav } from "./Nav";
import { Hero } from "./Hero";
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
        <Hero />
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
