import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import {
  Building2,
  Bell,
  Search,
  LogOut,
  ChevronDown,
  Sun,
  Moon,
  ShieldCheck,
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, activeTenant, switchTenant, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [tenantDropdownOpen, setTenantDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  return (
    <header className="h-16 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700/60 px-6 flex items-center justify-between shadow-sm z-20 transition-colors duration-200">
      {/* Left: Global Quick Search */}
      <div className="flex items-center space-x-4 flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar pólizas, facturas, clientes, SKUs... (Ctrl + K)"
            className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#047857]/30 focus:border-[#047857] transition-all"
          />
        </div>
      </div>

      {/* Right Controls: Tenant Switcher, Theme Toggle, Notifications, User Profile */}
      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Multi-Empresa Tenant Switcher */}
        <div className="relative">
          <button
            onClick={() => setTenantDropdownOpen(!tenantDropdownOpen)}
            className="flex items-center space-x-2 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-950/60 hover:bg-emerald-100/70 text-emerald-900 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/80 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
          >
            <Building2 className="w-4 h-4 text-[#047857] dark:text-emerald-400" />
            <div className="text-left max-w-[140px] truncate hidden sm:block">
              <span className="block truncate">{activeTenant ? activeTenant.legal_name : 'Seleccionar Empresa'}</span>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono block">
                {activeTenant?.rfc || ''}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 ml-1" />
          </button>

          {tenantDropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 py-2 z-50">
              <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                  Empresas / Tenants
                </p>
              </div>
              <div className="max-h-60 overflow-y-auto py-1">
                {user?.tenants.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      switchTenant(t.id);
                      setTenantDropdownOpen(false);
                    }}
                    className={`w-full text-left px-4 py-2.5 text-xs flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/60 transition-colors ${
                      t.id === activeTenant?.id
                        ? 'bg-emerald-50 dark:bg-emerald-950/60 font-semibold text-[#047857] dark:text-emerald-400'
                        : 'text-gray-700 dark:text-gray-200'
                    }`}
                  >
                    <div>
                      <div className="font-medium truncate max-w-[190px]">{t.legal_name}</div>
                      <div className="text-[10px] text-gray-400 font-mono">RFC: {t.rfc}</div>
                    </div>
                    {t.id === activeTenant?.id && (
                      <span className="w-2 h-2 rounded-full bg-[#047857]"></span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Global Dark / Light Mode Switcher */}
        <button
          onClick={toggleTheme}
          aria-label="Alternar Tema"
          className="p-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all shadow-sm cursor-pointer"
          title={isDark ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro'}
        >
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-gray-600" />
          )}
        </button>

        {/* Notifications Button */}
        <button
          className="relative p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors cursor-pointer"
          title="Notificaciones y Alertas Fiscales SAT"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white dark:ring-gray-800"></span>
        </button>

        {/* User Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center space-x-2 pl-2 pr-1 py-1 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
          >
            <div className="w-8 h-8 rounded-xl bg-[#047857] text-white font-bold flex items-center justify-center text-xs shadow-sm shadow-emerald-900/30">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="text-left hidden md:block">
              <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 block leading-tight">
                {user?.full_name}
              </span>
              <span className="text-[10px] text-gray-400 block leading-tight">
                {user?.is_superadmin ? 'Superadmin' : 'Usuario'}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
          </button>

          {userDropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 py-2 z-50">
              <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                  {user?.full_name}
                </p>
                <p className="text-[11px] text-gray-400 truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                <button
                  onClick={() => {
                    setUserDropdownOpen(false);
                    logout();
                  }}
                  className="w-full text-left px-4 py-2 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 flex items-center space-x-2 font-medium cursor-pointer"
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
