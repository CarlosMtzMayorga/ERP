import React from 'react';
import { PurchasesDashboardMetrics, PurchaseDocument } from '../types';
import {
  TrendingUp,
  Clock,
  AlertCircle,
  Users,
  ArrowUpRight,
  PlusCircle,
  FileText,
  UploadCloud,
  CheckCircle2,
  PackageCheck,
} from 'lucide-react';

interface Props {
  metrics: PurchasesDashboardMetrics | null;
  recentDocs: PurchaseDocument[];
  onOpenCreatePO: () => void;
  onGoToReception: () => void;
  onGoToXML: () => void;
}

export const PurchasesDashboardTab: React.FC<Props> = ({
  metrics,
  recentDocs,
  onOpenCreatePO,
  onGoToReception,
  onGoToXML,
}) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'BORRADOR':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">Borrador</span>;
      case 'AUTORIZADA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">Autorizada</span>;
      case 'PARCIALMENTE_RECIBIDA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">Parcial (Backorder)</span>;
      case 'RECIBIDA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">Recibida en Almacén</span>;
      case 'FACTURADA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">Facturada / Pasivo CxP</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  const getDocTypeBadge = (type: string) => {
    switch (type) {
      case 'ORDEN_COMPRA':
        return <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">OC</span>;
      case 'RECEPCION':
        return <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">REC</span>;
      case 'FACTURA_PROVEEDOR':
        return <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">FAC PROV</span>;
      default:
        return <span className="text-xs font-bold text-slate-600 bg-slate-50 px-2 py-0.5 rounded">{type}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* KPI Cards Header */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Compras del Mes */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Compras del Mes</p>
            <h3 className="text-2xl font-extrabold text-slate-900 mt-1">
              ${(metrics?.monthly_purchases_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </h3>
            <span className="text-xs font-medium text-emerald-600 flex items-center mt-1">
              <TrendingUp className="w-3.5 h-3.5 mr-1" /> Valuado al costo
            </span>
          </div>
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>

        {/* Metric 2: OCs Pendientes */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">OCs Pendientes de Surtir</p>
            <h3 className="text-2xl font-extrabold text-amber-600 mt-1">
              {metrics?.pending_purchase_orders_count || 0}
            </h3>
            <span className="text-xs font-medium text-amber-700 flex items-center mt-1">
              <Clock className="w-3.5 h-3.5 mr-1" /> Esperando almacén
            </span>
          </div>
          <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-xl flex items-center justify-center">
            <Clock className="w-6 h-6" />
          </div>
        </div>

        {/* Metric 3: Pasivos por Pagar (CxP) */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pasivos Pendientes (CxP)</p>
            <h3 className="text-2xl font-extrabold text-rose-600 mt-1">
              ${(metrics?.unpaid_invoices_balance || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </h3>
            <span className="text-xs font-medium text-rose-700 flex items-center mt-1">
              <AlertCircle className="w-3.5 h-3.5 mr-1" /> Saldo adeudado
            </span>
          </div>
          <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-xl flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
        </div>

        {/* Metric 4: Proveedores Activos */}
        <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Proveedores Activos</p>
            <h3 className="text-2xl font-extrabold text-slate-900 mt-1">
              {metrics?.active_suppliers_count || 0}
            </h3>
            <span className="text-xs font-medium text-slate-500 flex items-center mt-1">
              <Users className="w-3.5 h-3.5 mr-1" /> En padrón fiscal
            </span>
          </div>
          <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Action Banners */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          onClick={onOpenCreatePO}
          className="bg-gradient-to-br from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white p-5 rounded-2xl shadow-sm text-left flex items-start justify-between group transition-all"
        >
          <div>
            <span className="inline-block p-2 bg-white/10 rounded-xl mb-3">
              <PlusCircle className="w-5 h-5 text-white" />
            </span>
            <h4 className="font-bold text-base">Crear Orden de Compra</h4>
            <p className="text-xs text-blue-100 mt-1">Generar pedido formal a proveedor con precios pactados.</p>
          </div>
          <ArrowUpRight className="w-5 h-5 text-white/70 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
        </button>

        <button
          onClick={onGoToReception}
          className="bg-gradient-to-br from-emerald-600 to-teal-700 hover:from-emerald-700 hover:to-teal-800 text-white p-5 rounded-2xl shadow-sm text-left flex items-start justify-between group transition-all"
        >
          <div>
            <span className="inline-block p-2 bg-white/10 rounded-xl mb-3">
              <PackageCheck className="w-5 h-5 text-white" />
            </span>
            <h4 className="font-bold text-base">Recibir Mercancía</h4>
            <p className="text-xs text-emerald-100 mt-1">Entrada a almacén, escaneo de códigos y costeo PEPS/Promedio.</p>
          </div>
          <ArrowUpRight className="w-5 h-5 text-white/70 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
        </button>

        <button
          onClick={onGoToXML}
          className="bg-gradient-to-br from-slate-800 to-slate-900 hover:from-slate-900 hover:to-black text-white p-5 rounded-2xl shadow-sm text-left flex items-start justify-between group transition-all"
        >
          <div>
            <span className="inline-block p-2 bg-white/10 rounded-xl mb-3">
              <UploadCloud className="w-5 h-5 text-white" />
            </span>
            <h4 className="font-bold text-base">Importar XML CFDI 4.0</h4>
            <p className="text-xs text-slate-300 mt-1">Arrastra facturas de proveedores para conciliar y crear pasivo CxP.</p>
          </div>
          <ArrowUpRight className="w-5 h-5 text-white/70 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
        </button>
      </div>

      {/* Main Grid: Top Suppliers & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Suppliers */}
        <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-bold text-slate-900 flex items-center">
              <Users className="w-4 h-4 mr-2 text-blue-600" /> Principales Proveedores
            </h4>
            <span className="text-xs font-semibold text-slate-400">Por volumen</span>
          </div>

          <div className="space-y-4">
            {metrics?.top_suppliers && metrics.top_suppliers.length > 0 ? (
              metrics.top_suppliers.map((s, idx) => (
                <div key={s.supplier_id} className="p-3 bg-slate-50/80 rounded-xl border border-slate-100">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-bold text-slate-800 truncate max-w-[180px]">
                      {idx + 1}. {s.legal_name}
                    </span>
                    <span className="text-xs font-extrabold text-blue-600">
                      ${s.total_purchased.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-[11px] text-slate-500">
                    <span>RFC: {s.rfc}</span>
                    <span className="bg-white px-2 py-0.5 rounded border border-slate-200 font-medium">
                      {s.orders_count} compras
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-400 text-center py-6">No hay compras acumuladas en este periodo.</p>
            )}
          </div>
        </div>

        {/* Recent Purchases Activity */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-bold text-slate-900 flex items-center">
              <FileText className="w-4 h-4 mr-2 text-indigo-600" /> Movimientos Recientes de Compras
            </h4>
            <span className="text-xs font-semibold text-slate-400">Últimos documentos</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Folio</th>
                  <th className="py-2.5 px-3">Tipo</th>
                  <th className="py-2.5 px-3">Proveedor</th>
                  <th className="py-2.5 px-3">Fecha</th>
                  <th className="py-2.5 px-3 text-right">Total</th>
                  <th className="py-2.5 px-3 text-center">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentDocs.length > 0 ? (
                  recentDocs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-3 font-bold text-slate-900">{doc.formatted_folio}</td>
                      <td className="py-3 px-3">{getDocTypeBadge(doc.document_type)}</td>
                      <td className="py-3 px-3 text-slate-700 max-w-[200px] truncate">
                        {doc.supplier_name || 'Proveedor General'}
                      </td>
                      <td className="py-3 px-3 text-slate-500">
                        {new Date(doc.issue_date).toLocaleDateString('es-MX')}
                      </td>
                      <td className="py-3 px-3 text-right font-extrabold text-slate-900">
                        ${doc.total.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-3 text-center">{getStatusBadge(doc.status)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">
                      No se han emitido órdenes ni recepciones todavía.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
