import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { Toaster } from '@/components/ui/sonner';

// Layouts
import AdminLayout from '@/layouts/AdminLayout';
import TenantLayout from '@/layouts/TenantLayout';
import CustomerLayout from '@/layouts/CustomerLayout';

// Auth
import LoginPage from '@/pages/auth/LoginPage';

// Admin Pages
import AdminDashboard from '@/pages/admin/Dashboard';
import TenantsPage from '@/pages/admin/TenantsPage';
import UsersPage from '@/pages/admin/UsersPage';
import PolicyPage from '@/pages/admin/PolicyPage';
import SettingsPage from '@/pages/admin/SettingsPage';
import PeriodicJobsPage from '@/pages/admin/PeriodicJobsPage';
import IntegrationsPage from '@/pages/admin/IntegrationsPage';
import PromptsPage from '@/pages/admin/PromptsPage';

// Tenant Pages
import CasesPipeline from '@/pages/tenant/CasesPipeline';
import CaseDetail from '@/pages/tenant/CaseDetail';
import ScreeningQueue from '@/pages/tenant/ScreeningQueue';
import WaiversPage from '@/pages/tenant/WaiversPage';
import MIDashboard from '@/pages/tenant/MIDashboard';
import TenantSettings from '@/pages/tenant/TenantSettings';
import EDRPage from '@/pages/tenant/EDRPage';
import QAPage from '@/pages/tenant/QAPage';
import VideoIdentPage from '@/pages/tenant/VideoIdentPage';

// Customer Pages
import CustomerLanding from '@/pages/customer/CustomerLanding';
import CustomerDashboard from '@/pages/customer/CustomerDashboard';
import CustomerInvitePage from '@/pages/customer/CustomerInvitePage';
import Questionnaire from '@/pages/customer/Questionnaire';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-sm text-[#64748B]">Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  const { isAuthenticated, getPortal } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      
      {/* Admin Routes */}
      <Route path="/admin" element={<ProtectedRoute><AdminLayout /></ProtectedRoute>}>
        <Route index element={<AdminDashboard />} />
        <Route path="tenants" element={<TenantsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="policy" element={<PolicyPage />} />
        <Route path="jobs" element={<PeriodicJobsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      {/* Tenant Workspace Routes */}
      <Route path="/workspace" element={<ProtectedRoute><TenantLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/workspace/cases" replace />} />
        <Route path="cases" element={<CasesPipeline />} />
        <Route path="case/:caseId" element={<CaseDetail />} />
        <Route path="screening" element={<ScreeningQueue />} />
        <Route path="waivers" element={<WaiversPage />} />
        <Route path="edr" element={<EDRPage />} />
        <Route path="qa" element={<QAPage />} />
        <Route path="video-ident" element={<VideoIdentPage />} />
        <Route path="mi" element={<MIDashboard />} />
        <Route path="settings" element={<TenantSettings />} />
      </Route>

      {/* Customer Portal Routes */}
      <Route path="/portal" element={<CustomerLayout />}>
        <Route index element={<CustomerLanding />} />
        <Route path="invite/:token" element={<CustomerInvitePage />} />
        <Route path="dashboard" element={<ProtectedRoute><CustomerDashboard /></ProtectedRoute>} />
        <Route path="questionnaire" element={<ProtectedRoute><Questionnaire /></ProtectedRoute>} />
      </Route>

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
