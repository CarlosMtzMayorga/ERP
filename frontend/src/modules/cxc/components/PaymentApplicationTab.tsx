import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import { PendingReceivable } from '../types';
import {
  CreditCard,
  DollarSign,
  Calendar,
  Layers,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileCheck2,
  Building2,
  Clock,
  ArrowRight
} from 'lucide-react';

interface CustomerOption {
  id: string;
  code: string;
  legal_name: string;
  rfc: string;
  credit_limit: number;
  credit_days: number;
}

interface PaymentApplicationTabProps {
  initialCustomerId?: string;
  onPaymentSuccess: (receipt: any) => void;
}

export const PaymentApplicationTab: React.FC<PaymentApplicationTabProps> = ({
  initialCustomerId,
  onPaymentSuccess,
}) => {
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>(initialCustomerId || '');
  const [pendingDocs, setPendingDocs] = useState<PendingReceivable[]>([]);
  const [allocations, setAllocations] = useState<{ [receivableId: string]: string }>({});

  // Payment form state
  const [paymentAmount, setPaymentAmount] = useState<string>('');
  const [paymentForm, setPaymentForm] = useState<string>('03'); // 03 Transferencia
  const [operationNumber, setOperationNumber] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCustomers();
  }, []);

  useEffect(() => {
    if (selectedCustomerId) {
      loadPendingDocs(selectedCustomerId);
    } else {
      setPendingDocs([]);
      setAllocations({});
    }
  }, [selectedCustomerId]);

  const loadCustomers = async () => {
    try {
      // Query top debtors / customers
      const res = await apiClient.get('/cxc/dashboard');
      if (res.data?.top_debtors) {
        setCustomers(
          res.data.top_debtors.map((d: any) => ({
            id: d.customer_id,
            code: 'CLI',
            legal_name: d.customer_name,
            rfc: 'RFC',
            credit_limit: d.credit_limit,
            credit_days: d.credit_days,
          }))
        );
      }
    } catch (e) {
      console.error('Error loading customers for CxC:', e);
    }
  };

  const loadPendingDocs = async (customerId: string) => {
    setIsLoadingDocs(true);
    setError(null);
    try {
      const res = await apiClient.get<PendingReceivable[]>('/cxc/receivables/pending', {
        params: { customer_id: customerId },
      });
      setPendingDocs(res.data);

      // Reset allocations
      setAllocations({});
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al cargar facturas pendientes.');
    } finally {
      setIsLoadingDocs(false);
    }
  };

  const handleAllocationChange = (receivableId: string, val: string) => {
    setAllocations((prev) => ({
      ...prev,
      [receivableId]: val,
    }));
  };

  // Smart Distribution: "Abonar a la más antigua primero"
  const handleAutoDistribute = () => {
    const totalToDistribute = parseFloat(paymentAmount) || 0;
    if (totalToDistribute <= 0) {
      setError('Por favor ingrese el "Monto Total Recibido" antes de auto-distribuir.');
      return;
    }
    setError(null);

    let remaining = totalToDistribute;
    const newAllocations: { [receivableId: string]: string } = {};

    // Sort by due_date ascending (oldest first)
    const sorted = [...pendingDocs].sort(
      (a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
    );

    for (const doc of sorted) {
      if (remaining <= 0) {
        newAllocations[doc.id] = '0.00';
        continue;
      }
      const canPay = Math.min(remaining, doc.current_balance);
      newAllocations[doc.id] = canPay.toFixed(2);
      remaining -= canPay;
    }

    setAllocations(newAllocations);
  };

  // Calculations
  const totalAllocated = Object.values(allocations).reduce(
    (acc, val) => acc + (parseFloat(val) || 0),
    0
  );
  const targetAmount = parseFloat(paymentAmount) || 0;
  const difference = Math.round((targetAmount - totalAllocated) * 100) / 100;

  // Proportional Taxes Estimation (SAT REP 2.0)
  const propBase = Math.round((totalAllocated / 1.16) * 100) / 100;
  const propVat = Math.round((totalAllocated - propBase) * 100) / 100;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (targetAmount <= 0) {
      setError('El monto total del pago debe ser mayor a cero.');
      return;
    }

    if (Math.abs(difference) > 0.01) {
      setError(
        `La suma distribuida en facturas ($${totalAllocated.toFixed(2)}) no coincide con el total recibido ($${targetAmount.toFixed(2)}). Diferencia: $${difference.toFixed(2)}.`
      );
      return;
    }

    const payloadAllocations = Object.entries(allocations)
      .filter(([_, val]) => (parseFloat(val) || 0) > 0)
      .map(([id, val]) => ({
        receivable_id: id,
        amount_paid: parseFloat(val),
      }));

    if (payloadAllocations.length === 0) {
      setError('Debe asignar el abono al menos a una factura pendiente.');
      return;
    }

    setIsSubmitting(true);
    try {
      const branchId = localStorage.getItem('erp_branch_id') || '00000000-0000-0000-0000-000000000000';
      const payload = {
        branch_id: branchId,
        customer_id: selectedCustomerId,
        payment_form: paymentForm,
        amount: targetAmount,
        allocations: payloadAllocations,
        operation_number: operationNumber || undefined,
        notes: notes || undefined,
      };

      const res = await apiClient.post('/cxc/payments', payload);
      onPaymentSuccess(res.data);
      // Reload pending docs
      loadPendingDocs(selectedCustomerId);
      setPaymentAmount('');
      setOperationNumber('');
      setNotes('');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al aplicar el pago y timbrar el REP 2.0.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-start space-x-2 text-rose-700 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* TOP: CUSTOMER & PAYMENT DETAILS CARD */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-5">
        <div className="flex items-center space-x-3 pb-3 border-b border-slate-100">
          <div className="p-2 bg-blue-600 rounded-xl text-white">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Aplicación de Pago a Facturas PPD</h3>
            <p className="text-xs text-slate-500">
              Generación y timbrado de Complemento de Recepción de Pagos (REP 2.0 / CFDI 4.0)
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Customer Selector */}
          <div className="md:col-span-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Cliente / Deudor
            </label>
            <select
              value={selectedCustomerId}
              onChange={(e) => setSelectedCustomerId(e.target.value)}
              className="w-full text-xs font-bold px-3 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="">-- Seleccione un cliente para ver facturas --</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.legal_name} ({c.credit_days} días de crédito)
                </option>
              ))}
            </select>
          </div>

          {/* Monto Total Recibido */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Monto Total Recibido ($)
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 font-bold">$</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={paymentAmount}
                onChange={(e) => setPaymentAmount(e.target.value)}
                placeholder="0.00"
                className="w-full pl-8 pr-3 py-2 text-sm font-black rounded-xl border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
          </div>

          {/* Forma de Pago SAT */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Forma de Pago SAT
            </label>
            <select
              value={paymentForm}
              onChange={(e) => setPaymentForm(e.target.value)}
              className="w-full text-xs font-semibold px-3 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-800 focus:ring-2 focus:ring-blue-500"
            >
              <option value="03">03 - Transferencia Electrónica (SPEI)</option>
              <option value="01">01 - Efectivo</option>
              <option value="02">02 - Cheque Nominativo</option>
              <option value="04">04 - Tarjeta de Crédito</option>
              <option value="28">28 - Tarjeta de Débito</option>
            </select>
          </div>

          {/* Num Operacion */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Núm. Operación / Clave Rastreo
            </label>
            <input
              type="text"
              value={operationNumber}
              onChange={(e) => setOperationNumber(e.target.value)}
              placeholder="Ej. SPEI-88492048"
              className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 text-slate-800 focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Notes */}
          <div className="md:col-span-3">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Notas u Observaciones del Abono
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ej. Pago correspondiente a quincena de octubre"
              className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 text-slate-800 focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* PENDING INVOICES GRID */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Facturas PPD Pendientes ({pendingDocs.length})
            </h3>
            <p className="text-xs text-slate-500">
              Asigne el importe a liquidar para cada comprobante fiscal
            </p>
          </div>

          {pendingDocs.length > 0 && (
            <button
              type="button"
              onClick={handleAutoDistribute}
              className="py-2 px-3.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>Distribuir a la más antigua primero</span>
            </button>
          )}
        </div>

        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Folio Factura</th>
                <th className="py-3 px-4">Emisión</th>
                <th className="py-3 px-4">Vencimiento</th>
                <th className="py-3 px-4 text-center">Mora</th>
                <th className="py-3 px-4 text-right">Total Factura</th>
                <th className="py-3 px-4 text-right">Saldo Insoluto</th>
                <th className="py-3 px-4 text-right w-44">Importe a Abonar</th>
                <th className="py-3 px-4 text-right">Nuevo Saldo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoadingDocs ? (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-slate-400">
                    Cargando facturas pendientes del cliente...
                  </td>
                </tr>
              ) : pendingDocs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-slate-400">
                    {selectedCustomerId
                      ? 'Este cliente no tiene facturas PPD con saldo pendiente.'
                      : 'Seleccione un cliente para listar sus facturas.'}
                  </td>
                </tr>
              ) : (
                pendingDocs.map((doc) => {
                  const allocVal = parseFloat(allocations[doc.id] || '0') || 0;
                  const newBalance = Math.max(0, doc.current_balance - allocVal);

                  return (
                    <tr key={doc.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4">
                        <span className="font-bold text-slate-900 block">{doc.folio}</span>
                        {doc.cfdi_uuid && (
                          <span className="text-[10px] text-slate-400 font-mono truncate max-w-[120px] block">
                            {doc.cfdi_uuid}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-600">{doc.issue_date}</td>
                      <td className="py-3 px-4 text-slate-600">{doc.due_date}</td>
                      <td className="py-3 px-4 text-center">
                        {doc.is_overdue ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-700">
                            +{doc.days_overdue} días
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                            Vigente
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-medium text-slate-600">
                        ${Number(doc.original_total).toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-black text-slate-900">
                        ${Number(doc.current_balance).toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="relative">
                          <span className="absolute inset-y-0 left-0 pl-2 flex items-center text-slate-400 font-bold">$</span>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            max={doc.current_balance}
                            value={allocations[doc.id] || ''}
                            onChange={(e) => handleAllocationChange(doc.id, e.target.value)}
                            placeholder="0.00"
                            className="w-full text-right font-bold pl-6 pr-2 py-1.5 border border-slate-300 rounded-lg text-slate-900 focus:ring-1 focus:ring-blue-500"
                          />
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-slate-700">
                        ${newBalance.toFixed(2)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SAT PROPORTIONAL TAXES CARD & SUBMIT BAR */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 rounded-2xl p-6 text-white flex flex-col md:flex-row items-center justify-between gap-6 shadow-xl">
        <div className="space-y-1">
          <span className="text-[10px] uppercase font-bold tracking-widest text-indigo-400 block">
            Desglose Fiscal SAT (REP 2.0 / Anexo 20)
          </span>
          <div className="flex flex-wrap items-center gap-6 pt-1">
            <div>
              <span className="text-xs text-slate-400 block">Base Proporcional (BaseP):</span>
              <span className="text-base font-bold text-white">${propBase.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">IVA Proporcional 16% (ImporteP):</span>
              <span className="text-base font-bold text-indigo-300">+${propVat.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-xs text-slate-400 block">Total Distribuido:</span>
              <span className="text-xl font-black text-emerald-400">${totalAllocated.toFixed(2)}</span>
            </div>
          </div>
          {difference !== 0 && targetAmount > 0 && (
            <p className="text-[11px] text-amber-300 font-semibold pt-1">
              ⚠️ Falta distribuir: ${difference.toFixed(2)} para completar el pago total de ${targetAmount.toFixed(2)}.
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting || totalAllocated <= 0 || Math.abs(difference) > 0.01}
          className="py-4 px-6 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl font-black text-sm uppercase tracking-wider shadow-lg shadow-emerald-500/25 flex items-center justify-center space-x-2 transition shrink-0"
        >
          {isSubmitting ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          ) : (
            <>
              <CheckCircle2 className="w-5 h-5" />
              <span>Aplicar Pago y Timbrar REP 2.0</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </>
          )}
        </button>
      </div>
    </form>
  );
};
