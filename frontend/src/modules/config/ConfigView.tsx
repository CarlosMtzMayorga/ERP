import React, { useState } from 'react';
import {
  Settings,
  ShieldCheck,
  Layers,
  Users,
  Building2,
} from 'lucide-react';
import { CSDTab } from './components/CSDTab';
import { FoliosTab } from './components/FoliosTab';
import { UsersTab } from './components/UsersTab';
import { CompanyTab } from './components/CompanyTab';

type TabKey = 'company' | 'csd' | 'folios' | 'users';

export const ConfigView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('csd');

  const tabs = [
    { key: 'csd' as TabKey, label: 'Certificados CSD SAT', icon: ShieldCheck, badge: 'Fiscal' },
    { key: 'folios' as TabKey, label: 'Series y Folios', icon: Layers, badge: 'Atómico' },
    { key: 'users' as TabKey, label: 'Usuarios y Roles (RBAC)', icon: Users },
    { key: 'company' as TabKey, label: 'Empresa y Sucursales', icon: Building2 },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Title & Navigation Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Settings className="w-6 h-6 text-blue-600" />
            <span>Módulo 1: Configurador del Sistema</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Administración de certificados SAT CSD, series de folios atómicas y control de accesos RBAC.
          </p>
        </div>

        {/* Tab Switcher Pills */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-200/70 rounded-2xl border border-slate-200">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  isActive
                    ? 'bg-white text-blue-700 shadow-sm font-bold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-md ${
                    isActive ? 'bg-blue-100 text-blue-800' : 'bg-slate-300/60 text-slate-700'
                  }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content Display */}
      <div>
        {activeTab === 'csd' && <CSDTab />}
        {activeTab === 'folios' && <FoliosTab />}
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'company' && <CompanyTab />}
      </div>
    </div>
  );
};

