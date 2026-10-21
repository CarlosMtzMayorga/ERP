import React from 'react';
import { CxCDashboardData } from '../types';
import {
  Wallet,
  AlertTriangle,
  Clock,
  CheckCircle2,
  TrendingDown,
  Users,
  ShieldAlert,
  ArrowUpRight
} from 'lucide-react';

interface CxCDashboardTabProps {
  data: CxCDashboardData | null;
  isLoading: boolean;
  onSelectCustomer: (customerId: string) => void;
  onGoToPayment: () => void;
}

export const CxCDashboardTab: React.FC<CxCDashboardTabProps> = ({
  data,
  isLoading,
  onSelectCustomer,
  onGoToPayment,
}) => {
  if (isLoading || !data) {
    return (
      <div className="py-20 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-2">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        <span>Cargando métricas y análisis de cartera CxC...</span>
      </div>
    );
  }

  const buckets = data.buckets;
  const total = Number(data.total_receivable) || 1; // avoid / 0

  const getPercent = (amount: number) => {
    return Math.min(100, Math.round((Number(amount) / total) * 100));
  };

  return (
    <div className="space-y-6">
      {/* 4 TOP KPI CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Cartera */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
              Total Cartera por Cobrar
            </span>
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Wallet className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-black text-slate-900 tracking-tight">
              ${Number(data.total_receivable).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <span className="text-[11px] text-slate-500 mt-1 block">
              {data.total_pending_documents} facturas / documentos pendientes
            </span>
          </div>
        </div>

        {/* Cartera al Corriente */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
              Cartera al Corriente
            </span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-black text-emerald-700 tracking-tight">
              ${Number(data.current_receivable).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <span className="text-[11px] text-emerald-600 mt-1 block font-medium">
              {getPercent(data.current_receivable)}% dentro de plazo crediticio
            </span>
          </div>
        </div>

        {/* Cartera Vencida Total */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
              Cartera Vencida (Mora)
            </span>
            <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-black text-rose-600 tracking-tight">
              ${Number(data.overdue_total).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <span className="text-[11px] text-rose-600 mt-1 block font-bold">
              Facturas fuera de fecha de vencimiento
            </span>
          </div>
        </div>

        {/* % Morosidad */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
              Índice de Morosidad
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <TrendingDown className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-3xl font-black text-amber-700 tracking-tight">
              {Number(data.overdue_percentage).toFixed(1)}%
            </div>
            <span className="text-[11px] text-slate-500 mt-1 block">
              Meta empresarial: &lt; 8.0%
            </span>
          </div>
        </div>
      </div>

      {/* ANTIGÜEDAD DE SALDOS (AGING BREAKDOWN) */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Distribución de Antigüedad de Saldos Contable
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Segmentación oficial por rangos de morosidad estándar (Microsip & SAT)
            </p>
          </div>
          <button
            onClick={onGoToPayment}
            className="py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition shadow-sm flex items-center space-x-1.5"
          >
            <span>Aplicar Cobro (REP 2.0)</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Multi-segmented Progress Bar */}
        <div className="w-full h-4 bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
          <div
            style={{ width: `${getPercent(buckets.current)}%` }}
            className="bg-emerald-500 transition-all duration-500 hover:opacity-90"
            title={`Al Corriente: $${Number(buckets.current).toFixed(2)}`}
          ></div>
          <div
            style={{ width: `${getPercent(buckets.days_1_30)}%` }}
            className="bg-blue-500 transition-all duration-500 hover:opacity-90"
            title={`1 a 30 días: $${Number(buckets.days_1_30).toFixed(2)}`}
          ></div>
          <div
            style={{ width: `${getPercent(buckets.days_31_60)}%` }}
            className="bg-amber-400 transition-all duration-500 hover:opacity-90"
            title={`31 a 60 días: $${Number(buckets.days_31_60).toFixed(2)}`}
          ></div>
          <div
            style={{ width: `${getPercent(buckets.days_61_90)}%` }}
            className="bg-orange-500 transition-all duration-500 hover:opacity-90"
            title={`61 a 90 días: $${Number(buckets.days_61_90).toFixed(2)}`}
          ></div>
          <div
            style={{ width: `${getPercent(buckets.days_over_90)}%` }}
            className="bg-rose-600 transition-all duration-500 hover:opacity-90"
            title={`Más de 90 días: $${Number(buckets.days_over_90).toFixed(2)}`}
          ></div>
        </div>

        {/* Buckets Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-2">
          {/* Bucket 1: Al Corriente */}
          <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-emerald-800">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
              <span>Al Corriente</span>
            </div>
            <div className="mt-2 text-lg font-black text-slate-900">
              ${Number(buckets.current).toFixed(2)}
            </div>
            <span className="text-[10px] text-slate-500">{getPercent(buckets.current)}% del total</span>
          </div>

          {/* Bucket 2: 1-30 */}
          <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-blue-800">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
              <span>1 a 30 Días</span>
            </div>
            <div className="mt-2 text-lg font-black text-slate-900">
              ${Number(buckets.days_1_30).toFixed(2)}
            </div>
            <span className="text-[10px] text-slate-500">{getPercent(buckets.days_1_30)}% del total</span>
          </div>

          {/* Bucket 3: 31-60 */}
          <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-amber-800">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
              <span>31 a 60 Días</span>
            </div>
            <div className="mt-2 text-lg font-black text-slate-900">
              ${Number(buckets.days_31_60).toFixed(2)}
            </div>
            <span className="text-[10px] text-slate-500">{getPercent(buckets.days_31_60)}% del total</span>
          </div>

          {/* Bucket 4: 61-90 */}
          <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-orange-800">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
              <span>61 a 90 Días</span>
            </div>
            <div className="mt-2 text-lg font-black text-slate-900">
              ${Number(buckets.days_61_90).toFixed(2)}
            </div>
            <span className="text-[10px] text-slate-500">{getPercent(buckets.days_61_90)}% del total</span>
          </div>

          {/* Bucket 5: >90 */}
          <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-bold text-rose-800">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-600"></span>
              <span>&gt; 90 Días</span>
            </div>
            <div className="mt-2 text-lg font-black text-rose-700">
              ${Number(buckets.days_over_90).toFixed(2)}
            </div>
            <span className="text-[10px] text-rose-600 font-bold">{getPercent(buckets.days_over_90)}% crítico</span>
          </div>
        </div>
      </div>

      {/* TOP DEBTORS / CLIENTES DE MAYOR EXPOSICIÓN */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Users className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">Top Clientes con Mayor Saldo Pendiente</h3>
          </div>
          <span className="text-xs text-slate-500">Monitoreo de límites de crédito y exposición</span>
        </div>

        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Cliente / Razón Social</th>
                <th className="py-3 px-4 text-center">Días de Crédito</th>
                <th className="py-3 px-4 text-right">Límite de Crédito</th>
                <th className="py-3 px-4 text-right">Saldo Deudor Actual</th>
                <th className="py-3 px-4 text-center">Uso de Línea</th>
                <th className="py-3 px-4 text-center">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.top_debtors.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-slate-400">
                    No hay saldos pendientes de cobro registrados.
                  </td>
                </tr>
              ) : (
                data.top_debtors.map((debtor) => {
                  const limit = Number(debtor.credit_limit);
                  const debt = Number(debtor.total_debt);
                  const usage = limit > 0 ? Math.min(100, Math.round((debt / limit) * 100)) : 0;
                  const isOver = limit > 0 && debt > limit;

                  return (
                    <tr key={debtor.customer_id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 font-bold text-slate-900">
                        {debtor.customer_name}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700">
                          <Clock className="w-3 h-3 mr-1" />
                          {debtor.credit_days} días
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-medium text-slate-600">
                        ${limit > 0 ? limit.toFixed(2) : 'Sin límite (Contado)'}
                      </td>
                      <td className="py-3 px-4 text-right font-black text-slate-900">
                        ${debt.toFixed(2)}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2 max-w-[130px] mx-auto">
                          <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              style={{ width: `${usage}%` }}
                              className={`h-full rounded-full ${
                                isOver ? 'bg-rose-600' : (usage > 80 ? 'bg-amber-500' : 'bg-emerald-500')
                              }`}
                            ></div>
                          </div>
                          <span className={`text-[10px] font-bold ${isOver ? 'text-rose-600' : 'text-slate-600'}`}>
                            {usage}%
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => onSelectCustomer(debtor.customer_id)}
                          className="px-2.5 py-1 bg-slate-100 hover:bg-blue-50 hover:text-blue-600 rounded-lg text-slate-700 font-bold text-[11px] transition"
                        >
                          Ver Estado de Cuenta
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
