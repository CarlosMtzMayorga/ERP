import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  Building2,
  GitBranch,
  Bell,
  Search,
  LogOut,
  User as UserIcon,
  ChevronDown,
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, activeTenant, switchTenant, logout } = useAuth();
  const [tenantDropdownOpen, setTenantDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between shadow-soft z-20">
      {/* Left: Search & Breadcrumbs */}
      <div className="flex items-center space-x-4 flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar en catálogos, pólizas, facturas... (Ctrl + K)"
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
        </div>
      </div>

      {/* Right Controls: Tenant Switcher, Branch, Notifications, User */}
      <div className="flex items-center space-x-4">
        {/* Active Tenant / Multi-Empresa Switcher */}
        <div className="relative">
          <button
            onClick={() => setTenantDropdownOpen(!tenantDropdownOpen)}
            className="flex items-center space-x-2 px-3 py-2 bg-blue-50 hover:bg-blue-100/70 text-blue-900 border border-blue-200/60 rounded-xl text-xs font-semibold transition-colors"
          >
            <Building2 className="w-4 h-4 text-blue-600" />
            <div className="text-left max-w-[140px] truncate">
              <span className="block truncate">{activeTenant ? activeTenant.legal_name : 'Seleccionar Empresa'}</span>
              <span className="text-[10px] text-blue-600 font-mono block">{activeTenant?.rfc || ''}</span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-blue-500 ml-1" />
          </button>

          {tenantDropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-card border border-slate-100 py-2 z-50 animate-in fade-in zoom-in-95">
              <div className="px-4 py-2 border-b border-slate-100">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Empresas Disponibles</p>
              </div>
              <div className="max-h-60 overflow-y-auto py-1">
                {user?.tenants.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      switchTenant(t.id);
                      setTenantDropdownOpen(false);
                    }}
                    className={`w-full text-left px-4 py-2.5 text-xs flex items-center justify-between hover:bg-slate-50 transition-colors ${
                      t.id === activeTenant?.id ? 'bg-blue-50/70 font-semibold text-blue-600' : 'text-slate-700'
                    }`}
                  >
                    <div>
                      <div className="font-medium text-slate-900 truncate max-w-[180px]">{t.legal_name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">RFC: {t.rfc}</div>
                    </div>
                    {t.id === activeTenant?.id && (
                      <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Notifications */}
        <button
          className="relative p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
          title="Notificaciones y Alertas SAT"
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white"></span>
        </button>

        {/* User Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center space-x-3 pl-2 pr-1 py-1 rounded-xl hover:bg-slate-100 transition-colors"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white font-bold flex items-center justify-center text-sm shadow-sm">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="text-left hidden md:block">
              <span className="text-xs font-semibold text-slate-800 block leading-tight">{user?.full_name}</span>
              <span className="text-[11px] text-slate-500 block leading-tight">
                {user?.is_superadmin ? 'Superadministrador' : 'Usuario'}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {userDropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-card border border-slate-100 py-2 z-50">
              <div className="px-4 py-2 border-b border-slate-100">
                <p className="text-xs font-semibold text-slate-800 truncate">{user?.full_name}</p>
                <p className="text-[11px] text-slate-500 truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                <button
                  onClick={() => {
                    setUserDropdownOpen(false);
                    logout();
                  }}
                  className="w-full text-left px-4 py-2 text-xs text-rose-600 hover:bg-rose-50 flex items-center space-x-2 font-medium"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Cerrar Sesión</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

