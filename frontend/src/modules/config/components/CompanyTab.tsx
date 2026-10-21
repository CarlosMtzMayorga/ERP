import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  Building2,
  GitBranch,
  MapPin,
  Mail,
  Phone,
  ShieldCheck,
  Plus,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';

interface BranchItem {
  id: string;
  code: string;
  name: string;
  address?: string;
  zip_code: string;
  phone?: string;
  is_matrix: boolean;
  is_active: boolean;
}

interface TenantDetails {
  id: string;
  rfc: string;
  legal_name: string;
  trade_name?: string;
  fiscal_regime_code: string;
  zip_code: string;
  email?: string;
  phone?: string;
  status: string;
  plan: string;
  branches: BranchItem[];
}

export const CompanyTab: React.FC = () => {
  const [tenant, setTenant] = useState<TenantDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // New Branch Form
  const [branchCode, setBranchCode] = useState('');
  const [branchName, setBranchName] = useState('');
  const [branchAddress, setBranchAddress] = useState('');
  const [branchZip, setBranchZip] = useState('06000');
  const [branchPhone, setBranchPhone] = useState('');
  const [isMatrix, setIsMatrix] = useState(false);

  const fetchCompany = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<TenantDetails>('/tenants/current');
      setTenant(res.data);
    } catch (err) {
      console.error('Error fetching company:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompany();
  }, []);

  return (
    <div className="space-y-6">
      {/* Company Overview Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-soft">
        <div className="flex items-center justify-between pb-6 border-b border-slate-100">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-xl border border-blue-100">
              <Building2 className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900">{tenant?.legal_name || 'Cargando empresa...'}</h2>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  {tenant?.status === 'active' ? 'Empresa Activa' : tenant?.status}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                RFC: <strong className="text-slate-800">{tenant?.rfc}</strong> • Régimen Fiscal SAT: {tenant?.fiscal_regime_code} (General de Ley Personas Morales)
              </p>
            </div>
          </div>
          <button
            onClick={fetchCompany}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl"
            title="Refrescar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Código Postal Fiscal</span>
            <span className="text-sm font-bold text-slate-800 mt-1 block">{tenant?.zip_code}</span>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Plan SaaS Contratado</span>
            <span className="text-sm font-bold text-blue-600 uppercase mt-1 block">{tenant?.plan}</span>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Correo de Contacto</span>
            <span className="text-sm font-semibold text-slate-800 mt-1 block truncate">{tenant?.email || 'N/A'}</span>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Teléfono Conmutador</span>
            <span className="text-sm font-semibold text-slate-800 mt-1 block">{tenant?.phone || 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* Branches List */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-soft">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <GitBranch className="w-5 h-5 text-blue-600" />
              <span>Sucursales de la Empresa</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Control de almacenes, folios y cajas por sucursal</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tenant?.branches.map((b) => (
            <div
              key={b.id}
              className="p-4 rounded-xl border border-slate-200 hover:border-blue-200 bg-slate-50/50 hover:bg-blue-50/10 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                      {b.code}
                    </span>
                    <span className="font-bold text-slate-900 text-sm">{b.name}</span>
                    {b.is_matrix && (
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">
                        Matriz
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    <span>{b.address || 'Sin dirección registrada'} (C.P. {b.zip_code})</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

