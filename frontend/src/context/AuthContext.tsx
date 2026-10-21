import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/axiosClient';
import { UserProfile, TenantBrief, TokenResponse } from '../types/auth';

interface AuthContextType {
  user: UserProfile | null;
  activeTenant: TenantBrief | null;
  activeBranchId: string | null;
  permissions: string[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: TokenResponse) => void;
  logout: () => void;
  switchTenant: (tenantId: string, branchId?: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeTenant, setActiveTenant] = useState<TenantBrief | null>(null);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('erp_token');
      const savedTenantId = localStorage.getItem('erp_tenant_id');
      const savedBranchId = localStorage.getItem('erp_branch_id');

      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await apiClient.get<UserProfile>('/auth/me');
        setUser(response.data);

        if (response.data.tenants.length > 0) {
          const currentT = response.data.tenants.find((t) => t.id === savedTenantId) || response.data.tenants[0];
          setActiveTenant(currentT);
          localStorage.setItem('erp_tenant_id', currentT.id);
          setActiveBranchId(savedBranchId || currentT.default_branch_id || null);
        }
      } catch (err) {
        console.error('Failed to load session:', err);
        logout();
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = (data: TokenResponse) => {
    localStorage.setItem('erp_token', data.access_token);
    setUser(data.user);
    setPermissions(data.permissions);

    if (data.active_tenant_id) {
      localStorage.setItem('erp_tenant_id', data.active_tenant_id);
      const tenant = data.user.tenants.find((t) => t.id === data.active_tenant_id) || data.user.tenants[0] || null;
      setActiveTenant(tenant);
    }
    if (data.active_branch_id) {
      localStorage.setItem('erp_branch_id', data.active_branch_id);
      setActiveBranchId(data.active_branch_id);
    }
  };

  const logout = () => {
    localStorage.removeItem('erp_token');
    localStorage.removeItem('erp_tenant_id');
    localStorage.removeItem('erp_branch_id');
    setUser(null);
    setActiveTenant(null);
    setActiveBranchId(null);
    setPermissions([]);
  };

  const switchTenant = async (tenantId: string, branchId?: string) => {
    try {
      const res = await apiClient.post<TokenResponse>('/auth/switch-tenant', {
        tenant_id: tenantId,
        branch_id: branchId,
      });
      login(res.data);
    } catch (err) {
      console.error('Error switching tenant:', err);
      throw err;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        activeTenant,
        activeBranchId,
        permissions,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        switchTenant,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
