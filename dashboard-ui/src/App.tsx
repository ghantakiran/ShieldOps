import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import Layout from "./components/Layout";
import LandingLayout from "./components/landing/LandingLayout";
import { useAuthStore } from "./store/auth";
import { isDemoMode } from "./demo/config";
import { loginAsDemo } from "./demo/demoAuth";
import Landing from "./pages/Landing";
import ProductLanding from "./pages/ProductLanding";
import Pricing from "./pages/Pricing";
import Login from "./pages/Login";
import AgentFactory from "./pages/AgentFactory";
import AgentTask from "./pages/AgentTask";
import AgentHistory from "./pages/AgentHistory";
import WarRoom from "./pages/WarRoom";
import FleetOverview from "./pages/FleetOverview";
import Investigations from "./pages/Investigations";
import InvestigationDetail from "./pages/InvestigationDetail";
import Remediations from "./pages/Remediations";
import RemediationDetail from "./pages/RemediationDetail";
import Security from "./pages/Security";
import Cost from "./pages/Cost";
import Learning from "./pages/Learning";
import Analytics from "./pages/Analytics";
import AgentPerformance from "./pages/AgentPerformance";
import Settings from "./pages/Settings";
import VulnerabilityList from "./pages/VulnerabilityList";
import VulnerabilityDetailPage from "./pages/VulnerabilityDetail";
import AuditLog from "./pages/AuditLog";
import Playbooks from "./pages/Playbooks";
import PlaybookEditor from "./pages/PlaybookEditor";
import UserManagement from "./pages/UserManagement";
import IncidentTimeline from "./pages/IncidentTimeline";
import Billing from "./pages/Billing";
import SystemHealth from "./pages/SystemHealth";
import OnboardingWizard from "./pages/OnboardingWizard";
import Marketplace from "./pages/Marketplace";
import IncidentCorrelation from "./pages/IncidentCorrelation";
import ComplianceDashboard from "./pages/ComplianceDashboard";
import Predictions from "./pages/Predictions";
import CapacityForecast from "./pages/CapacityForecast";
import InfraAsCode from "./pages/InfraAsCode";
import SEOIndex from "./pages/SEOIndex";
import SEOPage from "./pages/SEOPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const [demoReady, setDemoReady] = useState(false);

  useEffect(() => {
    if (!isAuthenticated && isDemoMode()) {
      loginAsDemo();
      setDemoReady(true);
    }
  }, [isAuthenticated]);

  if (!isAuthenticated && isDemoMode() && !demoReady) {
    return null; // brief flash while demo auth initializes
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** Detects ?demo=true in the URL and persists it before rendering the app routes. */
function DemoDetector({ children }: { children: React.ReactNode }) {
  const [searchParams] = useSearchParams();
  useEffect(() => {
    if (searchParams.get("demo") === "true") {
      localStorage.setItem("shieldops_demo", "true");
    }
  }, [searchParams]);
  return <>{children}</>;
}

export default function App() {
  const { hydrate } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <BrowserRouter>
      <DemoDetector>
        <Routes>
          {/* Public routes with landing layout */}
          <Route element={<LandingLayout />}>
            <Route index element={<Landing />} />
            <Route path="products/:productId" element={<ProductLanding />} />
            <Route path="pricing" element={<Pricing />} />
            <Route path="solutions" element={<SEOIndex />} />
            <Route path="solutions/:slug" element={<SEOPage />} />
          </Route>

          {/* Standalone public routes */}
          <Route path="/landing" element={<Navigate to="/" replace />} />
          <Route path="/login" element={<Login />} />

          {/* Dashboard routes under /app */}
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AgentFactory />} />
            <Route path="agent-task" element={<AgentTask />} />
            <Route path="war-room" element={<WarRoom />} />
            <Route path="agent-history" element={<AgentHistory />} />
            <Route path="fleet" element={<FleetOverview />} />
            <Route path="investigations" element={<Investigations />} />
            <Route path="investigations/:id" element={<InvestigationDetail />} />
            <Route path="investigations/:id/timeline" element={<IncidentTimeline />} />
            <Route path="remediations" element={<Remediations />} />
            <Route path="remediations/:id" element={<RemediationDetail />} />
            <Route path="security" element={<Security />} />
            <Route path="vulnerabilities" element={<VulnerabilityList />} />
            <Route path="vulnerabilities/:id" element={<VulnerabilityDetailPage />} />
            <Route path="cost" element={<Cost />} />
            <Route path="learning" element={<Learning />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="agent-performance" element={<AgentPerformance />} />
            <Route path="marketplace" element={<Marketplace />} />
            <Route path="playbooks" element={<Playbooks />} />
            <Route path="playbooks/editor" element={<PlaybookEditor />} />
            <Route path="playbooks/editor/:id" element={<PlaybookEditor />} />
            <Route path="audit-log" element={<AuditLog />} />
            <Route path="compliance" element={<ComplianceDashboard />} />
            <Route path="billing" element={<Billing />} />
            <Route path="system-health" element={<SystemHealth />} />
            <Route path="settings" element={<Settings />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="incidents" element={<IncidentCorrelation />} />
            <Route path="predictions" element={<Predictions />} />
            <Route path="capacity" element={<CapacityForecast />} />
            <Route path="infra-as-code" element={<InfraAsCode />} />
            <Route path="onboarding" element={<OnboardingWizard />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </DemoDetector>
    </BrowserRouter>
  );
}
