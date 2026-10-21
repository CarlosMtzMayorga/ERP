import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { MainLayout } from './components/layout/MainLayout';
import { LoginView } from './modules/auth/LoginView';
import { DashboardView } from './modules/dashboard/DashboardView';
import { ConfigView } from './modules/config/ConfigView';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-900 text-white text-sm">
        <div className="flex flex-col items-center space-y-3">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-slate-400 text-xs">Cargando sesión ERP SaaS...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginView />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardView />} />
            <Route path="config" element={<ConfigView />} />
            {/* Placeholders for upcoming modules in next phases */}
            <Route path="inventory" element={<DashboardView />} />
            <Route path="sales" element={<DashboardView />} />
            <Route path="pos" element={<DashboardView />} />
            <Route path="cxc" element={<DashboardView />} />
            <Route path="purchases" element={<DashboardView />} />
            <Route path="cxp" element={<DashboardView />} />
            <Route path="banking" element={<DashboardView />} />
            <Route path="payroll" element={<DashboardView />} />
            <Route path="accounting" element={<DashboardView />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};
export default App;

