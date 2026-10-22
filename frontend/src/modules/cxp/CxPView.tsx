import React, { useState, useEffect } from 'react';
import {
  PaymentScheduleItem,
  PaymentScheduleSummary,
  CxPDashboardMetrics,
  SupplierPayment,
} from './types';
import { BankAccount } from '../banking/types';
import { apiClient } from '../../api/axiosClient';
import {
  Wallet,
  LayoutDashboard,
  Calendar,
  CreditCard,
  History,
  AlertTriangle,
  Clock,
  CheckCircle2,
  TrendingDown,
  Building2,
  Search,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  Landmark,
  Layers,
} from 'lucide-react';

export const CxPView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'schedule' | 'payment_manager' | 'history'>('dashboard');
  const [loading, setLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState<CxPDashboardMetrics | null>(null);
  const [schedule, setSchedule] = useState<PaymentScheduleSummary | null>(null);
  const [paymentsHistory, setPaymentsHistory] = useState<SupplierPayment[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);

  // Payment Manager State
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>('');
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [sourceBankAccountId, setSourceBankAccountId] = useState<string>('');
  const [branchId, setBranchId] = useState<string>('');
  const [paymentAmount, setPaymentAmount] = useState<number>(0);
  const [operationNumber, setOperationNumber] = useState<string>('');
  const [paymentNotes, setPaymentNotes] = useState<string>('');
  const [submittingPayment, setSubmittingPayment] = useState<boolean>(false);

  // Filters
  const [scheduleSearch, setScheduleSearch] = useState<string>('');
  const [scheduleFilter, setScheduleFilter] = useState<string>('ALL');

  const fetchCxPData = async () => {
    setLoading(true);
    try {
      const [metricsRes, scheduleRes, paymentsRes, bankAccsRes, suppRes, branchRes] = await Promise.all([
        apiClient.get<CxPDashboardMetrics>('/cxp/dashboard').catch(() => ({ data: null })),
        apiClient.get<PaymentScheduleSummary>('/cxp/schedule').catch(() => ({ data: null })),
        apiClient.get<SupplierPayment[]>('/cxp/payments').catch(() => ({ data: [] })),
        apiClient.get<BankAccount[]>('/banking/accounts').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/tenants/suppliers').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/tenants/branches').catch(() => ({ data: [] })),
      ]);

      setMetrics(metricsRes.data);
      setSchedule(scheduleRes.data);
      setPaymentsHistory(paymentsRes.data);
      setBankAccounts(bankAccsRes.data);
      setSuppliers(suppRes.data);
      setBranches(branchRes.data);

      if (bankAccsRes.data.length > 0 && !sourceBankAccountId) {
        setSourceBankAccountId(bankAccsRes.data[0].id);
      }
      if (branchRes.data.length > 0 && !branchId) {
        setBranchId(branchRes.data[0].id);
      }
    } catch (err) {
      console.error('Error fetching CxP data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCxPData();
  }, []);

  // Filter pending docs for the payment manager based on selected supplier
  const supplierPendingDocs = (schedule?.items || []).filter(
    (item) => !selectedSupplierId || item.supplier_id === selectedSupplierId
  );

  // Toggle selection of documents to pay
  const toggleSelectDoc = (docId: string) => {
    const updated = new Set(selectedDocIds);
    if (updated.has(docId)) {
      updated.delete(docId);
    } else {
      updated.add(docId);
    }
    setSelectedDocIds(updated);

    // Auto-sum selected documents' current balance
    const sum = (schedule?.items || [])
      .filter((d) => updated.has(d.id))
      .reduce((acc, d) => acc + Number(d.current_balance), 0);
    setPaymentAmount(sum);
  };

  const handleSelectAllSupplierDocs = () => {
    if (selectedDocIds.size === supplierPendingDocs.length) {
      setSelectedDocIds(new Set());
      setPaymentAmount(0);
    } else {
      const allIds = new Set(supplierPendingDocs.map((d) => d.id));
      setSelectedDocIds(allIds);
      const sum = supplierPendingDocs.reduce((acc, d) => acc + Number(d.current_balance), 0);
      setPaymentAmount(sum);
    }
  };

  const handleExecutePayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSupplierId) {
      alert('Seleccione el proveedor al que realizará el pago.');
      return;
    }
    if (!sourceBankAccountId) {
      alert('Seleccione la cuenta bancaria de origen para extraer los fondos.');
      return;
    }
    if (paymentAmount <= 0) {
      alert('El monto del pago debe ser mayor a cero.');
      return;
    }

    // Check bank account balance
    const selectedBank = bankAccounts.find((b) => b.id === sourceBankAccountId);
    if (selectedBank && paymentAmount > selectedBank.current_balance) {
      alert(
        `Control de Sobregiro: Fondos insuficientes en ${selectedBank.bank_name}. Saldo disponible: $${selectedBank.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })}, Monto a pagar: $${paymentAmount.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
      );
      return;
    }

    setSubmittingPayment(true);
    try {
      const distributions = Array.from(selectedDocIds).map((docId) => {
        const doc = (schedule?.items || []).find((d) => d.id === docId);
        return {
          payable_document_id: docId,
          amount_to_apply: doc ? Number(doc.current_balance) : 0,
        };
      });

      await apiClient.post('/cxp/payments', {
        supplier_id: selectedSupplierId,
        branch_id: branchId,
        bank_account_id: sourceBankAccountId,
        amount: Number(paymentAmount),
        payment_method: '03',
        operation_number: operationNumber,
        notes: paymentNotes,
        distributions: distributions.length > 0 ? distributions : null,
      });

      alert('¡Pago a proveedor aplicado y descontado de bancos exitosamente!');
      setSelectedDocIds(new Set());
      setPaymentAmount(0);
      setOperationNumber('');
      setPaymentNotes('');
      await fetchCxPData();
      setActiveTab('history');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al aplicar el pago a proveedor.');
    } finally {
      setSubmittingPayment(false);
    }
  };

  const selectedBankAccount = bankAccounts.find((b) => b.id === sourceBankAccountId);

  // Filtered schedule items for the calendar view
  const filteredScheduleItems = (schedule?.items || []).filter((item) => {
    const matchesSearch =
      item.formatted_folio.toLowerCase().includes(scheduleSearch.toLowerCase()) ||
      item.supplier_name.toLowerCase().includes(scheduleSearch.toLowerCase()) ||
      item.supplier_rfc.toLowerCase().includes(scheduleSearch.toLowerCase());

    if (scheduleFilter === 'OVERDUE') return matchesSearch && item.is_overdue;
    if (scheduleFilter === 'TODAY') return matchesSearch && item.days_until_due === 0;
    if (scheduleFilter === 'WEEK') return matchesSearch && item.days_until_due > 0 && item.days_until_due <= 7;
    if (scheduleFilter === 'LATER') return matchesSearch && item.days_until_due > 7;
    return matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Title & Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 bg-rose-600 text-white rounded-xl shadow-md shadow-rose-500/20">
              <Wallet className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
              Cuentas por Pagar (CxP)
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Programación de vencimientos, calendario de pagos a proveedores y liquidación atómica con bancos.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setActiveTab('payment_manager')}
            className="inline-flex items-center px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold shadow-sm transition-colors"
          >
            <CreditCard className="w-4 h-4 mr-1.5" /> Pagar Facturas a Proveedor
          </button>

          <button
            onClick={fetchCxPData}
            disabled={loading}
            className="p-2 bg-white border border-slate-200 text-slate-600 hover:text-rose-600 rounded-xl text-xs font-semibold shadow-2xs hover:bg-slate-50 transition-colors"
            title="Actualizar datos"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-slate-200 space-x-2 overflow-x-auto pb-px">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'dashboard'
              ? 'border-rose-600 text-rose-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Dashboard CxP</span>
        </button>

        <button
          onClick={() => setActiveTab('schedule')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'schedule'
              ? 'border-rose-600 text-rose-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Calendario de Vencimientos</span>
        </button>

        <button
          onClick={() => setActiveTab('payment_manager')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'payment_manager'
              ? 'border-rose-600 text-rose-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Gestor de Pagos (Egresos)</span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'history'
              ? 'border-rose-600 text-rose-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Historial de Pagos ({paymentsHistory.length})</span>
        </button>
      </div>

      {/* TAB 1: DASHBOARD CXP */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pasivo Total Adeudado</p>
                <h3 className="text-2xl font-extrabold text-slate-900 mt-1">
                  ${(metrics?.total_accounts_payable || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-slate-500 flex items-center mt-1">
                  <Clock className="w-3.5 h-3.5 mr-1" /> Cartera pasiva CxP
                </span>
              </div>
              <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-xl flex items-center justify-center">
                <Wallet className="w-6 h-6" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Adeudo Vencido</p>
                <h3 className="text-2xl font-extrabold text-rose-600 mt-1">
                  ${(metrics?.overdue_payable || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-rose-700 flex items-center mt-1">
                  <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Fuera de crédito
                </span>
              </div>
              <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-xl flex items-center justify-center">
                <AlertTriangle className="w-6 h-6" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pagado Este Mes</p>
                <h3 className="text-2xl font-extrabold text-emerald-600 mt-1">
                  ${(metrics?.paid_this_month || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-emerald-700 flex items-center mt-1">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Transferido a proveedores
                </span>
              </div>
              <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center">
                <TrendingDown className="w-6 h-6" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Acreedores con Saldo</p>
                <h3 className="text-2xl font-extrabold text-slate-900 mt-1">
                  {metrics?.active_creditors_count || 0}
                </h3>
                <span className="text-xs font-medium text-slate-500 flex items-center mt-1">
                  <Building2 className="w-3.5 h-3.5 mr-1" /> Proveedores pendientes
                </span>
              </div>
              <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                <Building2 className="w-6 h-6" />
              </div>
            </div>
          </div>

          {/* Schedule Breakdown Cards */}
          <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
            <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center">
              <Calendar className="w-4 h-4 mr-2 text-rose-600" /> Próximos Vencimientos por Antigüedad
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="p-4 bg-rose-50/70 border border-rose-200 rounded-2xl">
                <span className="text-xs font-bold text-rose-800 uppercase block">Vencido</span>
                <span className="text-xl font-extrabold text-rose-600 mt-1 block">
                  ${(metrics?.schedule_summary.overdue_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </span>
                <span className="text-[11px] text-rose-700">Prioridad inmediata</span>
              </div>

              <div className="p-4 bg-amber-50/70 border border-amber-200 rounded-2xl">
                <span className="text-xs font-bold text-amber-800 uppercase block">Vence Hoy</span>
                <span className="text-xl font-extrabold text-amber-600 mt-1 block">
                  ${(metrics?.schedule_summary.due_today_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </span>
                <span className="text-[11px] text-amber-700">Exigible al corte</span>
              </div>

              <div className="p-4 bg-blue-50/70 border border-blue-200 rounded-2xl">
                <span className="text-xs font-bold text-blue-800 uppercase block">Esta Semana (1-7 días)</span>
                <span className="text-xl font-extrabold text-blue-600 mt-1 block">
                  ${(metrics?.schedule_summary.due_this_week_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </span>
                <span className="text-[11px] text-blue-700">Programar fondos</span>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl">
                <span className="text-xs font-bold text-slate-700 uppercase block">A Futuro (&gt; 7 días)</span>
                <span className="text-xl font-extrabold text-slate-900 mt-1 block">
                  ${(metrics?.schedule_summary.due_later_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </span>
                <span className="text-[11px] text-slate-500">Al corriente</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CALENDARIO DE VENCIMIENTOS */}
      {activeTab === 'schedule' && (
        <div className="space-y-6">
          <div className="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm w-full">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Buscar por folio, proveedor o RFC..."
                value={scheduleSearch}
                onChange={(e) => setScheduleSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-rose-500/20"
              />
            </div>

            <select
              value={scheduleFilter}
              onChange={(e) => setScheduleFilter(e.target.value)}
              className="py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700"
            >
              <option value="ALL">Todos los Vencimientos</option>
              <option value="OVERDUE">Solo Vencidos</option>
              <option value="TODAY">Vence Hoy</option>
              <option value="WEEK">Vence Esta Semana</option>
              <option value="LATER">A Futuro</option>
            </select>
          </div>

          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-4">Folio Factura</th>
                    <th className="py-3 px-4">Proveedor / RFC</th>
                    <th className="py-3 px-4">Fecha Emisión</th>
                    <th className="py-3 px-4">Vencimiento</th>
                    <th className="py-3 px-4 text-center">Días Restantes</th>
                    <th className="py-3 px-4 text-right">Saldo Insoluto</th>
                    <th className="py-3 px-4 text-center">Semáforo</th>
                    <th className="py-3 px-4 text-center">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredScheduleItems.length > 0 ? (
                    filteredScheduleItems.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="py-3 px-4 font-bold text-slate-900">{item.formatted_folio}</td>
                        <td className="py-3 px-4">
                          <p className="font-bold text-slate-800">{item.supplier_name}</p>
                          <p className="text-[11px] text-slate-400">{item.supplier_rfc}</p>
                        </td>
                        <td className="py-3 px-4 text-slate-500">
                          {new Date(item.issue_date).toLocaleDateString('es-MX')}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-800">
                          {new Date(item.due_date).toLocaleDateString('es-MX')}
                        </td>
                        <td className="py-3 px-4 text-center font-bold">
                          {item.is_overdue ? (
                            <span className="text-rose-600">{Math.abs(item.days_until_due)} días de atraso</span>
                          ) : item.days_until_due === 0 ? (
                            <span className="text-amber-600">Hoy</span>
                          ) : (
                            <span className="text-slate-600">{item.days_until_due} días</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right font-extrabold text-slate-900">
                          ${item.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {item.is_overdue ? (
                            <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-700">
                              Vencido
                            </span>
                          ) : item.days_until_due <= 7 ? (
                            <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
                              Por Vencer
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                              Al Corriente
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => {
                              setSelectedSupplierId(item.supplier_id);
                              setSelectedDocIds(new Set([item.id]));
                              setPaymentAmount(item.current_balance);
                              setActiveTab('payment_manager');
                            }}
                            className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg text-xs font-bold transition-colors"
                          >
                            Pagar
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-10 text-center text-slate-400">
                        No hay facturas pendientes que coincidan con los filtros.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: GESTOR DE PAGOS A PROVEEDORES (EGRESOS) */}
      {activeTab === 'payment_manager' && (
        <form onSubmit={handleExecutePayment} className="space-y-6">
          {/* Header Configuration */}
          <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-bold text-slate-700 mb-1">Proveedor a Pagar *</label>
              <select
                required
                value={selectedSupplierId}
                onChange={(e) => {
                  setSelectedSupplierId(e.target.value);
                  setSelectedDocIds(new Set());
                  setPaymentAmount(0);
                }}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold text-slate-800"
              >
                <option value="">-- Seleccione proveedor con saldo --</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.legal_name} ({s.rfc})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-bold text-slate-700 mb-1">Cuenta Bancaria de Origen (Retiro) *</label>
              <select
                required
                value={sourceBankAccountId}
                onChange={(e) => setSourceBankAccountId(e.target.value)}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold text-slate-800"
              >
                {bankAccounts.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.bank_name} - {b.account_number} (Disp: ${b.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })})
                  </option>
                ))}
              </select>
              {selectedBankAccount && (
                <p className="text-[11px] text-emerald-600 font-medium mt-1">
                  Saldo disponible en banco: ${selectedBankAccount.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </p>
              )}
            </div>

            <div>
              <label className="block font-bold text-slate-700 mb-1">Clave SPEI / No. Cheque</label>
              <input
                type="text"
                value={operationNumber}
                onChange={(e) => setOperationNumber(e.target.value)}
                placeholder="SPEI-001928475"
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-mono"
              />
            </div>
          </div>

          {/* Invoices Selection Grid */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={supplierPendingDocs.length > 0 && selectedDocIds.size === supplierPendingDocs.length}
                  onChange={handleSelectAllSupplierDocs}
                  className="w-4 h-4 rounded text-rose-600 focus:ring-rose-500"
                />
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Facturas Pendientes del Proveedor ({supplierPendingDocs.length})
                </h4>
              </div>
              <span className="text-[11px] text-slate-400">
                Seleccione las facturas que se liquidarán con esta transferencia
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                  <tr>
                    <th className="py-2.5 px-3 w-10"></th>
                    <th className="py-2.5 px-3">Folio</th>
                    <th className="py-2.5 px-3">Emisión</th>
                    <th className="py-2.5 px-3">Vencimiento</th>
                    <th className="py-2.5 px-3 text-right">Total Factura</th>
                    <th className="py-2.5 px-3 text-right">Ret. IVA</th>
                    <th className="py-2.5 px-3 text-right">Saldo Insoluto</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {supplierPendingDocs.length > 0 ? (
                    supplierPendingDocs.map((doc) => {
                      const isSelected = selectedDocIds.has(doc.id);
                      return (
                        <tr
                          key={doc.id}
                          onClick={() => toggleSelectDoc(doc.id)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? 'bg-rose-50/70' : 'hover:bg-slate-50/50'
                          }`}
                        >
                          <td className="py-3 px-3 text-center">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}}
                              className="w-4 h-4 rounded text-rose-600 pointer-events-none"
                            />
                          </td>
                          <td className="py-3 px-3 font-bold text-slate-900">{doc.formatted_folio}</td>
                          <td className="py-3 px-3 text-slate-500">
                            {new Date(doc.issue_date).toLocaleDateString('es-MX')}
                          </td>
                          <td className="py-3 px-4 font-bold text-slate-800">
                            {new Date(doc.due_date).toLocaleDateString('es-MX')}
                          </td>
                          <td className="py-3 px-3 text-right text-slate-600">
                            ${doc.original_total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-3 text-right text-slate-500 font-medium">
                            ${doc.original_retention_vat.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-3 text-right font-extrabold text-rose-600">
                            ${doc.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        {selectedSupplierId
                          ? 'No hay facturas pendientes para este proveedor.'
                          : 'Seleccione un proveedor para consultar sus facturas adeudadas.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Payment Summary & Confirmation Bar */}
          <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex-1 space-y-1">
              <span className="text-xs font-semibold text-slate-400 block">Total a Transferir al Proveedor:</span>
              <div className="flex items-center space-x-3">
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  required
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(Number(e.target.value))}
                  className="w-48 p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-extrabold text-base text-right text-rose-600 focus:ring-2 focus:ring-rose-500/20"
                />
                <span className="text-xs text-slate-500 font-medium">
                  {selectedDocIds.size} facturas seleccionadas
                </span>
              </div>
            </div>

            <button
              type="submit"
              disabled={submittingPayment || paymentAmount <= 0}
              className="w-full md:w-auto px-6 py-3 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold shadow-md shadow-rose-500/20 flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>{submittingPayment ? 'Aplicando Pago...' : 'Ejecutar Pago a Proveedor (Egreso Bancario)'}</span>
            </button>
          </div>
        </form>
      )}

      {/* TAB 4: HISTORIAL DE PAGOS */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Historial de Transferencias y Comprobantes de Pago
            </h4>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-3 px-4">Folio Pago</th>
                  <th className="py-3 px-4">Proveedor</th>
                  <th className="py-3 px-4">Banco Origen</th>
                  <th className="py-3 px-4">Fecha Pago</th>
                  <th className="py-3 px-4">Referencia SPEI</th>
                  <th className="py-3 px-4 text-center">Facturas Saldadas</th>
                  <th className="py-3 px-4 text-right">Monto Pagado</th>
                  <th className="py-3 px-4 text-center">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paymentsHistory.length > 0 ? (
                  paymentsHistory.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4 font-bold text-slate-900">{p.formatted_folio}</td>
                      <td className="py-3 px-4 font-medium text-slate-800">{p.supplier_name || 'Proveedor'}</td>
                      <td className="py-3 px-4 text-slate-600">{p.bank_name || 'Banco'}</td>
                      <td className="py-3 px-4 text-slate-500">
                        {new Date(p.payment_date).toLocaleDateString('es-MX')}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-500">{p.operation_number || 'S/R'}</td>
                      <td className="py-3 px-4 text-center font-bold text-slate-700">{p.related_docs.length}</td>
                      <td className="py-3 px-4 text-right font-extrabold text-rose-600">
                        ${p.amount.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                          {p.status}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="py-10 text-center text-slate-400">
                      No se han emitido pagos a proveedores todavía.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

