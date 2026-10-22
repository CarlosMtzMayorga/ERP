import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Settings,
  Boxes,
  ShoppingCart,
  Receipt,
  CreditCard,
  Truck,
  Wallet,
  Landmark,
  Users,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';

interface NavItem {
  name: string;
  path: string;
  icon: React.ElementType;
  badge?: string;
}

const navItems: NavItem[] = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: '1. Configurador', path: '/config', icon: Settings },
  { name: '2. Inventarios', path: '/inventory', icon: Boxes },
  { name: '3. Ventas', path: '/sales', icon: ShoppingCart },
  { name: '4. Punto de Venta (POS)', path: '/pos', icon: Receipt },
  { name: '5. Cuentas por Cobrar', path: '/cxc', icon: CreditCard },
  { name: '6. Compras', path: '/purchases', icon: Truck },
  { name: '7. Cuentas por Pagar', path: '/cxp', icon: Wallet },
  { name: '8. Bancos', path: '/banking', icon: Landmark },
  { name: '9. Nómina', path: '/payroll', icon: Users },
  { name: '10. Contabilidad', path: '/accounting', icon: BookOpen },
];

export const Sidebar: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(false);

  return (
    <aside
      className={`bg-slate-900 text-slate-300 flex flex-col transition-all duration-300 border-r border-slate-800/80 select-none z-30 shadow-xl ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800/80">
        {!collapsed && (
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-[#047857] flex items-center justify-center text-white shadow-lg shadow-emerald-900/40">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-white text-lg tracking-tight block">ERP SaaS</span>
              <span className="text-[10px] text-emerald-400 font-medium uppercase tracking-wider block">
                Empresarial CFDI 4.0
              </span>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="w-full flex justify-center">
            <div className="w-10 h-10 rounded-xl bg-[#047857] flex items-center justify-center text-white shadow-md shadow-emerald-900/30">
              <ShieldCheck className="w-6 h-6" />
            </div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition-colors ${
            collapsed ? 'hidden' : 'block'
          }`}
          title={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
      </div>

      {/* Module Navigation List */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1 custom-scrollbar">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                  isActive
                    ? 'bg-[#047857] text-white shadow-md shadow-emerald-950/40 font-semibold'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/80'
                }`
              }
            >
              <Icon className="w-5 h-5 flex-shrink-0 group-hover:scale-105 transition-transform" />
              {!collapsed && <span className="truncate">{item.name}</span>}
              {!collapsed && item.badge && (
                <span className="ml-auto text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer Info / Collapsed Toggle */}
      <div className="p-3 border-t border-slate-800/80">
        {collapsed ? (
          <button
            onClick={() => setCollapsed(false)}
            className="w-full py-2 flex justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            title="Expandir menú"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        ) : (
          <div className="px-3 py-2 rounded-xl bg-slate-800/50 border border-slate-700/50 text-[11px] text-slate-400 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              SAT 2026 Online
            </span>
            <span className="font-mono text-emerald-400 font-medium">v1.2.0</span>
          </div>
        )}
      </div>
    </aside>
  );
};
