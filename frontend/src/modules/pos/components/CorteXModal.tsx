import React from 'react';
import { CorteXData } from '../types';
import { FileText, X, DollarSign, CreditCard, ArrowDownRight, ArrowUpRight, Clock, User, Printer } from 'lucide-react';

interface CorteXModalProps {
  data: CorteXData | null;
  isOpen: boolean;
  onClose: () => void;
}

export const CorteXModal: React.FC<CorteXModalProps> = ({ data, isOpen, onClose }) => {
  if (!isOpen || !data) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-slate-900 p-5 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-600 rounded-lg">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-bold">Corte X (Lectura Parcial)</h3>
              <p className="text-xs text-slate-400">Auditoría en tiempo real sin cierre de turno</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Metadata */}
          <div className="bg-slate-50 rounded-xl p-3 grid grid-cols-2 gap-2 text-xs text-slate-600 border border-slate-200">
            <div className="flex items-center space-x-1.5">
              <User className="w-3.5 h-3.5 text-slate-400" />
              <span><strong>Cajero:</strong> {data.cashier_name}</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span><strong>Apertura:</strong> {new Date(data.opened_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          </div>

          {/* Expected Cash Highlight */}
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 text-center">
            <span className="text-xs uppercase tracking-wider text-blue-700 font-bold">Efectivo Físico Esperado en Caja</span>
            <div className="text-3xl font-black text-blue-900 mt-1">
              ${data.expected_cash.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MXN
            </div>
            <span className="text-[11px] text-blue-600 mt-1 block">Fondo + Ventas Efectivo + Entradas - Retiros</span>
          </div>

          {/* Breakdown List */}
          <div className="space-y-2.5 text-sm divide-y divide-slate-100">
            <div className="flex justify-between items-center pt-2">
              <span className="text-slate-600">Fondo Inicial de Apertura:</span>
              <span className="font-semibold text-slate-900">${data.initial_cash.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center pt-2">
              <span className="text-slate-600 flex items-center space-x-1">
                <DollarSign className="w-4 h-4 text-emerald-600" />
                <span>Ventas en Efectivo:</span>
              </span>
              <span className="font-semibold text-emerald-700">+${data.cash_sales.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center pt-2">
              <span className="text-slate-600 flex items-center space-x-1">
                <CreditCard className="w-4 h-4 text-indigo-600" />
                <span>Ventas con Tarjeta:</span>
              </span>
              <span className="font-semibold text-indigo-700">${data.card_sales.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center pt-2">
              <span className="text-slate-600 flex items-center space-x-1">
                <ArrowUpRight className="w-4 h-4 text-emerald-600" />
                <span>Entradas de Cambio:</span>
              </span>
              <span className="font-semibold text-emerald-700">+${data.cash_entries.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center pt-2">
              <span className="text-slate-600 flex items-center space-x-1">
                <ArrowDownRight className="w-4 h-4 text-rose-600" />
                <span>Retiros de Efectivo:</span>
              </span>
              <span className="font-semibold text-rose-700">-${data.cash_withdrawals.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center pt-2 font-bold">
              <span className="text-slate-800">Total Ventas ({data.tickets_count} tickets):</span>
              <span className="text-blue-700">${data.total_sales.toFixed(2)}</span>
            </div>
          </div>

          <div className="pt-2 flex gap-3">
            <button
              onClick={() => window.print()}
              type="button"
              className="flex-1 py-2.5 px-3 rounded-xl border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-bold flex items-center justify-center space-x-2 transition"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimir Corte X</span>
            </button>
            <button
              onClick={onClose}
              type="button"
              className="flex-1 py-2.5 px-3 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition"
            >
              Entendido / Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

