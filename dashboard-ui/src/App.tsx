import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import Layout from "./components/Layout";
import { useAuthStore } from "./store/auth";
import Login from "./pages/Login";
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

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const { hydrate } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<FleetOverview />} />
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
          <Route path="playbooks" element={<Playbooks />} />
          <Route path="playbooks/editor" element={<PlaybookEditor />} />
          <Route path="playbooks/editor/:id" element={<PlaybookEditor />} />
          <Route path="audit-log" element={<AuditLog />} />
          <Route path="billing" element={<Billing />} />
          <Route path="system-health" element={<SystemHealth />} />
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={<UserManagement />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
