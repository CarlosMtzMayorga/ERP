import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  FileCheck2,
  X,
  Layers,
  Calendar,
  CheckCircle2,
  AlertCircle,
  FileCode,
  ShieldCheck,
  Receipt
} from 'lucide-react';

interface PendingTicket {
  id: string;
  folio: string;
  total: number;
  payment_method: string;
  created_at: string;
}

interface GlobalInvoiceModalProps {
  branchId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const GlobalInvoiceModal: React.FC<GlobalInvoiceModalProps> = ({
  branchId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [tickets, setTickets] = useState<PendingTicket[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [periodicity, setPeriodicity] = useState<string>('01'); // 01=Diaria
  const [months, setMonths] = useState<string>(('0' + (new Date().getMonth() + 1)).slice(-2));
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadPendingTickets();
      setResult(null);
      setError(null);
    }
  }, [isOpen]);

  const loadPendingTickets = async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.get('/pos/global-invoice/pending-tickets', {
        params: { branch_id: branchId },
      });
      const ticketList: PendingTicket[] = res.data.tickets || [];
      setTickets(ticketList);
      setSelectedIds(ticketList.map((t) => t.id));
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al cargar tickets pendientes.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const toggleSelectAll = () => {
    if (selectedIds.length === tickets.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(tickets.map((t) => t.id));
    }
  };

  const toggleSelectTicket = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Selected totals & breakdown
  const selectedTickets = tickets.filter((t) => selectedIds.includes(t.id));
  const totalGross = selectedTickets.reduce((acc, t) => acc + t.total, 0);
  const baseSubtotal = Math.round((totalGross / 1.16) * 100) / 100;
  const vatAmount = Math.round((totalGross - baseSubtotal) * 100) / 100;

  const handleGenerateInvoice = async () => {
    if (selectedIds.length === 0) {
      setError('Debe seleccionar al menos un ticket para generar la factura global.');
      return;
    }
    setError(null);
    setIsSubmitting(true);

    try {
      const payload = {
        branch_id: branchId,
        periodicity,
        months,
        year,
        ticket_ids: selectedIds,
      };
      const res = await apiClient.post('/pos/global-invoice/generate', payload);
      setResult(res.data);
      onSuccess();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al generar la Factura Global CFDI 4.0.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden border border-slate-200 my-8 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-indigo-950 p-5 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-600 rounded-xl">
              <FileCheck2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-bold">Facturación Global CFDI 4.0</h3>
              <p className="text-xs text-indigo-300">
                Público en General (RFC XAXX010101000) con nodo InformacionGlobal
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-indigo-300 hover:text-white p-1 rounded-lg hover:bg-indigo-900 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-start space-x-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {result ? (
            <div className="space-y-4 text-center py-4">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
                <ShieldCheck className="w-9 h-9" />
              </div>
              <h4 className="text-lg font-bold text-slate-900">¡Factura Global Timbrada con Éxito!</h4>
              <p className="text-xs text-slate-600 max-w-md mx-auto">
                El comprobante fiscal digital ha sido sellado criptográficamente y timbrado por el PAC.
              </p>

              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-left max-w-md mx-auto space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500 font-semibold">Folio Asignado:</span>
                  <span className="font-bold text-slate-800">{result.folio}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-semibold">UUID Fiscal SAT:</span>
                  <span className="font-mono font-bold text-indigo-700 text-[11px] truncate max-w-[240px]">
                    {result.uuid}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-semibold">Total Facturado:</span>
                  <span className="font-bold text-emerald-700 text-sm">${result.total?.toFixed(2)} MXN</span>
                </div>
              </div>

              <div className="pt-3 flex gap-3 justify-center">
                <button
                  type="button"
                  onClick={onClose}
                  className="py-2.5 px-6 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-xs transition"
                >
                  Finalizar
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Configuration Grid */}
              <div className="grid grid-cols-3 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
                    Periodicidad SAT
                  </label>
                  <select
                    value={periodicity}
                    onChange={(e) => setPeriodicity(e.target.value)}
                    className="w-full text-xs font-semibold px-2.5 py-2 border border-slate-300 rounded-lg bg-white"
                  >
                    <option value="01">01 - Diaria</option>
                    <option value="02">02 - Semanal</option>
                    <option value="03">03 - Quincenal</option>
                    <option value="04">04 - Mensual</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
                    Mes
                  </label>
                  <select
                    value={months}
                    onChange={(e) => setMonths(e.target.value)}
                    className="w-full text-xs font-semibold px-2.5 py-2 border border-slate-300 rounded-lg bg-white"
                  >
                    {Array.from({ length: 12 }, (_, i) => {
                      const m = ('0' + (i + 1)).slice(-2);
                      return (
                        <option key={m} value={m}>
                          {m} - {new Date(2026, i).toLocaleString('es-MX', { month: 'long' })}
                        </option>
                      );
                    })}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
                    Año
                  </label>
                  <input
                    type="number"
                    value={year}
                    onChange={(e) => setYear(parseInt(e.target.value) || 2026)}
                    className="w-full text-xs font-semibold px-2.5 py-2 border border-slate-300 rounded-lg bg-white text-center"
                  />
                </div>
              </div>

              {/* Tickets Table / Multi-select */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-bold text-slate-700 uppercase tracking-wider">
                    Tickets Pendientes ({tickets.length})
                  </span>
                  <button
                    type="button"
                    onClick={toggleSelectAll}
                    className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
                  >
                    {selectedIds.length === tickets.length ? 'Deseleccionar Todos' : 'Seleccionar Todos'}
                  </button>
                </div>

                <div className="max-h-52 overflow-y-auto border border-slate-200 rounded-xl divide-y divide-slate-100 bg-white">
                  {isLoading ? (
                    <div className="p-8 text-center text-xs text-slate-400">Cargando tickets pendientes...</div>
                  ) : tickets.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-400">
                      No hay tickets pendientes de facturación global.
                    </div>
                  ) : (
                    tickets.map((t) => {
                      const isChecked = selectedIds.includes(t.id);
                      return (
                        <div
                          key={t.id}
                          onClick={() => toggleSelectTicket(t.id)}
                          className={`p-3 flex items-center justify-between text-xs cursor-pointer transition select-none ${
                            isChecked ? 'bg-indigo-50/60' : 'hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-center space-x-3">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {}} // Handled by div click
                              className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4"
                            />
                            <div>
                              <span className="font-bold text-slate-800">{t.folio}</span>
                              <span className="text-[10px] text-slate-400 ml-2">
                                {new Date(t.created_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })} ({t.payment_method})
                              </span>
                            </div>
                          </div>
                          <span className="font-bold text-slate-900">${t.total.toFixed(2)}</span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Mathematical Reverse VAT Breakdown Card */}
              <div className="bg-gradient-to-r from-slate-900 to-indigo-950 rounded-2xl p-4 text-white">
                <span className="text-[10px] uppercase tracking-widest text-indigo-300 font-bold block mb-2">
                  Desglose Fiscal SAT (Anexo 20 CFDI 4.0)
                </span>
                <div className="grid grid-cols-3 gap-4 text-center divide-x divide-white/10">
                  <div>
                    <span className="text-xs text-slate-400 block">Base Gravable</span>
                    <span className="text-base font-bold">${baseSubtotal.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-xs text-slate-400 block">IVA Trasladado (16%)</span>
                    <span className="text-base font-bold text-indigo-300">+${vatAmount.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-xs text-emerald-400 block font-bold">Total Factura</span>
                    <span className="text-lg font-black text-emerald-400">${totalGross.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 py-3 px-4 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-xs transition"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleGenerateInvoice}
                  disabled={isSubmitting || selectedIds.length === 0}
                  className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-xl font-bold text-xs shadow-lg shadow-indigo-600/25 flex items-center justify-center space-x-2 transition"
                >
                  {isSubmitting ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Timbrar Factura Global ({selectedIds.length} tickets)</span>
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
