import HeroSection from "../components/landing/HeroSection";
import ProblemSection from "../components/landing/ProblemSection";
import SolutionSection from "../components/landing/SolutionSection";
import HowItWorks from "../components/landing/HowItWorks";
import ProductsSection from "../components/landing/ProductsSection";
import BenefitsSection from "../components/landing/BenefitsSection";
import IntegrationsSection from "../components/landing/IntegrationsSection";
import SafetySection from "../components/landing/SafetySection";
import CTASection from "../components/landing/CTASection";

export default function Landing() {
  return (
    <div className="pt-20">
      <HeroSection />
      <ProblemSection />
      <SolutionSection />
      <HowItWorks />
      <ProductsSection />
      <BenefitsSection />
      <IntegrationsSection />
      <SafetySection />
      <CTASection />
    </div>
  );
}
