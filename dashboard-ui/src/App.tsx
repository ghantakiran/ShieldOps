import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import { lazy, Suspense, useEffect, useState } from "react";
import Layout from "./components/Layout";
import LandingLayout from "./components/landing/LandingLayout";
import LoadingSpinner from "./components/LoadingSpinner";
import { useAuthStore } from "./store/auth";
import { isDemoMode } from "./demo/config";
import { loginAsDemo } from "./demo/demoAuth";

// ── Eagerly loaded (critical path) ─────────────────────────────────
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import AgentFactory from "./pages/AgentFactory";

// ── Lazy-loaded pages ──────────────────────────────────────────────
const ProductLanding = lazy(() => import("./pages/ProductLanding"));
const Pricing = lazy(() => import("./pages/Pricing"));
const SEOIndex = lazy(() => import("./pages/SEOIndex"));
const SEOPage = lazy(() => import("./pages/SEOPage"));
const AgentTask = lazy(() => import("./pages/AgentTask"));
const AgentHistory = lazy(() => import("./pages/AgentHistory"));
const WarRoom = lazy(() => import("./pages/WarRoom"));
const FleetOverview = lazy(() => import("./pages/FleetOverview"));
const Investigations = lazy(() => import("./pages/Investigations"));
const InvestigationDetail = lazy(() => import("./pages/InvestigationDetail"));
const Remediations = lazy(() => import("./pages/Remediations"));
const RemediationDetail = lazy(() => import("./pages/RemediationDetail"));
const Security = lazy(() => import("./pages/Security"));
const Cost = lazy(() => import("./pages/Cost"));
const Learning = lazy(() => import("./pages/Learning"));
const Analytics = lazy(() => import("./pages/Analytics"));
const AgentPerformance = lazy(() => import("./pages/AgentPerformance"));
const Settings = lazy(() => import("./pages/Settings"));
const VulnerabilityList = lazy(() => import("./pages/VulnerabilityList"));
const VulnerabilityDetailPage = lazy(() => import("./pages/VulnerabilityDetail"));
const AuditLog = lazy(() => import("./pages/AuditLog"));
const Playbooks = lazy(() => import("./pages/Playbooks"));
const PlaybookEditor = lazy(() => import("./pages/PlaybookEditor"));
const UserManagement = lazy(() => import("./pages/UserManagement"));
const IncidentTimeline = lazy(() => import("./pages/IncidentTimeline"));
const Billing = lazy(() => import("./pages/Billing"));
const SystemHealth = lazy(() => import("./pages/SystemHealth"));
const OnboardingWizard = lazy(() => import("./pages/OnboardingWizard"));
const Marketplace = lazy(() => import("./pages/Marketplace"));
const IncidentCorrelation = lazy(() => import("./pages/IncidentCorrelation"));
const ComplianceDashboard = lazy(() => import("./pages/ComplianceDashboard"));
const Predictions = lazy(() => import("./pages/Predictions"));
const CapacityForecast = lazy(() => import("./pages/CapacityForecast"));
const InfraAsCode = lazy(() => import("./pages/InfraAsCode"));
const PipelineRuns = lazy(() => import("./pages/PipelineRuns"));
const APIKeys = lazy(() => import("./pages/APIKeys"));
const Workflows = lazy(() => import("./pages/Workflows"));
const ScheduledTasks = lazy(() => import("./pages/ScheduledTasks"));

// ── Suspense fallback ──────────────────────────────────────────────

function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <LoadingSpinner />
    </div>
  );
}

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
        <Suspense fallback={<PageLoader />}>
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
              <Route path="schedules" element={<ScheduledTasks />} />
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
              <Route path="pipeline" element={<PipelineRuns />} />
              <Route path="api-keys" element={<APIKeys />} />
              <Route path="workflows" element={<Workflows />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </DemoDetector>
    </BrowserRouter>
  );
}
