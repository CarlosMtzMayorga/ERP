import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import { CustomerStatement } from '../types';
import {
  FileText,
  Printer,
  Download,
  Calendar,
  DollarSign,
  User,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';

interface AccountStatementTabProps {
  initialCustomerId?: string;
}

export const AccountStatementTab: React.FC<AccountStatementTabProps> = ({ initialCustomerId }) => {
  const [customerId, setCustomerId] = useState<string>(initialCustomerId || '');
  const [customers, setCustomers] = useState<any[]>([]);
  const [statement, setStatement] = useState<CustomerStatement | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    loadCustomers();
  }, []);

  useEffect(() => {
    if (customerId) {
      loadStatement(customerId);
    }
  }, [customerId]);

  const loadCustomers = async () => {
    try {
      const res = await apiClient.get('/cxc/dashboard');
      if (res.data?.top_debtors) {
        setCustomers(res.data.top_debtors);
        if (!customerId && res.data.top_debtors.length > 0) {
          setCustomerId(res.data.top_debtors[0].customer_id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadStatement = async (id: string) => {
    setIsLoading(true);
    try {
      const res = await apiClient.get<CustomerStatement>(`/cxc/customers/${id}/statement`);
      setStatement(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Customer Selector & Actions */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex-1 min-w-[280px]">
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
            Seleccionar Cliente
          </label>
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            className="w-full text-xs font-bold px-3 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-800 focus:ring-2 focus:ring-blue-500"
          >
            {customers.map((c) => (
              <option key={c.customer_id} value={c.customer_id}>
                {c.customer_name} (Saldo: ${Number(c.total_debt).toFixed(2)})
              </option>
            ))}
          </select>
        </div>

        <div className="flex gap-2 pt-4 md:pt-0">
          <button
            onClick={() => window.print()}
            className="py-2.5 px-4 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 transition shadow"
          >
            <Printer className="w-4 h-4" />
            <span>Imprimir Estado de Cuenta</span>
          </button>
        </div>
      </div>

      {/* FORMAL PRINTABLE STATEMENT */}
      {statement && (
        <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm space-y-6 print:p-0 print:border-0 print:shadow-none">
          {/* Statement Header */}
          <div className="flex justify-between items-start pb-6 border-b border-slate-200">
            <div>
              <span className="text-xs uppercase font-extrabold tracking-widest text-blue-600 block">
                ERP SAAS FINANCIAL MEXICO
              </span>
              <h2 className="text-2xl font-black text-slate-900 mt-1">Estado de Cuenta de Clientes</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Cuentas por Cobrar & Resumen de Antigüedad
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs font-bold text-slate-400 block">Fecha de Emisión:</span>
              <span className="text-xs font-bold text-slate-700">
                {new Date().toLocaleDateString('es-MX', { year: 'numeric', month: 'long', day: 'numeric' })}
              </span>
            </div>
          </div>

          {/* Customer Info Box */}
          <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-slate-400 block font-bold uppercase text-[10px]">Razón Social</span>
              <span className="font-extrabold text-slate-900 text-sm">{statement.customer.legal_name}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-bold uppercase text-[10px]">RFC Cliente</span>
              <span className="font-mono font-bold text-slate-800">{statement.customer.rfc}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-bold uppercase text-[10px]">Límite / Días Crédito</span>
              <span className="font-bold text-slate-800">
                ${Number(statement.customer.credit_limit).toFixed(2)} ({statement.customer.credit_days} días)
              </span>
            </div>
            <div>
              <span className="text-slate-400 block font-bold uppercase text-[10px]">Saldo Deudor Actual</span>
              <span className="font-black text-rose-600 text-base">
                ${Number(statement.customer.current_balance).toFixed(2)} MXN
              </span>
            </div>
          </div>

          {/* Transactions Ledger */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-white uppercase text-[11px] tracking-wider font-semibold">
                <tr>
                  <th className="py-3 px-4">Fecha</th>
                  <th className="py-3 px-4">Tipo</th>
                  <th className="py-3 px-4">Folio / Documento</th>
                  <th className="py-3 px-4">Concepto</th>
                  <th className="py-3 px-4 text-right">Cargo (+)</th>
                  <th className="py-3 px-4 text-right">Abono (-)</th>
                  <th className="py-3 px-4 text-right">Saldo Insoluto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      Cargando movimientos contables...
                    </td>
                  </tr>
                ) : statement.transactions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      No hay cargos o abonos registrados para este cliente.
                    </td>
                  </tr>
                ) : (
                  statement.transactions.map((tx, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 text-slate-600">
                        {tx.date ? new Date(tx.date).toLocaleDateString('es-MX') : '-'}
                      </td>
                      <td className="py-3 px-4">
                        {tx.type === 'CARGO' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                            CARGO
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            ABONO
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-800">{tx.folio}</td>
                      <td className="py-3 px-4 text-slate-700">{tx.concept}</td>
                      <td className="py-3 px-4 text-right font-semibold text-slate-900">
                        {tx.type === 'CARGO' ? `$${tx.amount.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-emerald-700">
                        {tx.type === 'ABONO' ? `$${tx.amount.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-3 px-4 text-right font-black text-slate-900">
                        ${tx.balance.toFixed(2)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Footer note */}
          <div className="pt-4 border-t border-slate-100 flex justify-between text-[11px] text-slate-400">
            <span>Comprobante generado por ERP SaaS Cloud México (CFDI 4.0)</span>
            <span>Página 1 de 1</span>
          </div>
        </div>
      )}
    </div>
  );
};

