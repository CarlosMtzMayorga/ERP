import React, { useState } from 'react';
import {
  Settings,
  ShieldCheck,
  Layers,
  Users,
  Building2,
} from 'lucide-react';
import { motion } from 'framer-motion';
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
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="space-y-6 max-w-7xl mx-auto font-sans"
    >
      {/* Page Title & Navigation Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] flex items-center justify-center">
              <Settings className="w-5 h-5 text-[#047857]" />
            </div>
            <span>Módulo 1: Configurador del Sistema</span>
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Administración de certificados SAT CSD, series de folios atómicas y control de accesos RBAC.
          </p>
        </div>

        {/* Tab Switcher Pills */}
        <div className="flex items-center gap-1.5 p-1 bg-gray-100 dark:bg-gray-900/80 rounded-2xl border border-gray-200 dark:border-gray-700/80">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  isActive
                    ? 'bg-white dark:bg-gray-800 text-[#047857] dark:text-emerald-400 shadow-sm font-bold'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-[#047857] dark:text-emerald-400' : 'text-gray-400'}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                    isActive
                      ? 'bg-emerald-100 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300'
                      : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
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
    </motion.div>
  );
};

export default ConfigView;
