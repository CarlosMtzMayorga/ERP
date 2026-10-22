import React, { useState } from 'react';
import { PayableDocument } from '../types';
import {
  CreditCard,
  Search,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Building2,
} from 'lucide-react';

interface Props {
  payables: PayableDocument[];
}

export const AccountsPayableTab: React.FC<Props> = ({ payables }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filtered = payables.filter((p) => {
    const matchesSearch =
      p.formatted_folio.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.supplier_name && p.supplier_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (p.supplier_rfc && p.supplier_rfc.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesStatus = statusFilter === 'ALL' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalOutstanding = payables
    .filter((p) => p.status === 'PENDIENTE' || p.status === 'PARCIAL')
    .reduce((acc, p) => acc + Number(p.current_balance), 0);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PENDIENTE':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-700">Pendiente de Pago</span>;
      case 'PARCIAL':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">Parcial</span>;
      case 'LIQUIDADO':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">Liquidado</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-xl flex items-center justify-center">
            <CreditCard className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-800">Pasivos por Pagar (Cuentas por Pagar - CxP)</h3>
            <p className="text-xs text-slate-500">Facturas de proveedores registradas manualmente o importadas vía XML del SAT.</p>
          </div>
        </div>

        <div className="text-right">
          <span className="text-xs font-semibold text-slate-400">Total Pasivo Exigible:</span>
          <h4 className="text-xl font-extrabold text-rose-600">
            ${totalOutstanding.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </h4>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-100 shadow-sm">
        <div className="relative flex-1 max-w-sm w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar por folio, proveedor o RFC..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-rose-500/20"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 focus:outline-none"
        >
          <option value="ALL">Todos los Estados</option>
          <option value="PENDIENTE">Pendientes</option>
          <option value="PARCIAL">Parciales</option>
          <option value="LIQUIDADO">Liquidados</option>
        </select>
      </div>

      {/* Payables Table */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-3 px-4">Folio Factura</th>
                <th className="py-3 px-4">Proveedor / Razón Social</th>
                <th className="py-3 px-4">Emisión</th>
                <th className="py-3 px-4">Vencimiento</th>
                <th className="py-3 px-4 text-center">Días Crédito</th>
                <th className="py-3 px-4 text-right">Total Facturado</th>
                <th className="py-3 px-4 text-right">Saldo Insoluto</th>
                <th className="py-3 px-4 text-center">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length > 0 ? (
                filtered.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4">
                      <p className="font-bold text-slate-900">{item.formatted_folio}</p>
                      {item.cfdi_uuid && (
                        <p className="text-[10px] text-slate-400 font-mono truncate max-w-[120px]">
                          {item.cfdi_uuid}
                        </p>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      <p className="font-bold text-slate-800">{item.supplier_name || 'Proveedor'}</p>
                      <p className="text-[11px] text-slate-500">{item.supplier_rfc}</p>
                    </td>

                    <td className="py-3 px-4 text-slate-500">
                      {new Date(item.issue_date).toLocaleDateString('es-MX')}
                    </td>

                    <td className="py-3 px-4 font-semibold text-slate-700">
                      {new Date(item.due_date).toLocaleDateString('es-MX')}
                    </td>

                    <td className="py-3 px-4 text-center font-bold text-slate-600">
                      {item.credit_days} días
                    </td>

                    <td className="py-3 px-4 text-right text-slate-700">
                      ${Number(item.original_total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>

                    <td className="py-3 px-4 text-right font-extrabold text-rose-600">
                      ${Number(item.current_balance).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>

                    <td className="py-3 px-4 text-center">
                      {getStatusBadge(item.status)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    No se encontraron pasivos de proveedores registrados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

