import React, { useState, useEffect } from 'react';
import {
  BankAccount,
  BankTransaction,
  BankingDashboardMetrics,
} from './types';
import { apiClient } from '../../api/axiosClient';
import {
  Landmark,
  LayoutDashboard,
  Scale,
  ArrowLeftRight,
  PlusCircle,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  Clock,
  Search,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
  Building2,
  Wallet,
  ArrowUpRight,
  ArrowDownLeft,
  X,
} from 'lucide-react';

export const BankingView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'reconciliation' | 'transfers'>('dashboard');
  const [loading, setLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState<BankingDashboardMetrics | null>(null);
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [currencies, setCurrencies] = useState<any[]>([]);

  // Reconciliation state
  const [selectedAccForReconciliation, setSelectedAccForReconciliation] = useState<string>('');
  const [unreconciledTxs, setUnreconciledTxs] = useState<BankTransaction[]>([]);
  const [selectedTxIds, setSelectedTxIds] = useState<Set<string>>(new Set());
  const [reconciling, setReconciling] = useState<boolean>(false);

  // Transfer modal
  const [showTransferModal, setShowTransferModal] = useState<boolean>(false);
  const [sourceAccId, setSourceAccId] = useState<string>('');
  const [targetAccId, setTargetAccId] = useState<string>('');
  const [transferAmount, setTransferAmount] = useState<number>(0);
  const [transferOpNum, setTransferOpNum] = useState<string>('');
  const [transferNotes, setTransferNotes] = useState<string>('');
  const [submittingTransfer, setSubmittingTransfer] = useState<boolean>(false);

  // New Account modal
  const [showNewAccountModal, setShowNewAccountModal] = useState<boolean>(false);
  const [newBankName, setNewBankName] = useState<string>('');
  const [newAccNumber, setNewAccNumber] = useState<string>('');
  const [newClabe, setNewClabe] = useState<string>('');
  const [newCurrencyId, setNewCurrencyId] = useState<string>('');
  const [newInitialBalance, setNewInitialBalance] = useState<number>(0);
  const [submittingAccount, setSubmittingAccount] = useState<boolean>(false);

  const fetchBankingData = async () => {
    setLoading(true);
    try {
      const [metricsRes, accountsRes, txsRes, currRes] = await Promise.all([
        apiClient.get<BankingDashboardMetrics>('/banking/dashboard').catch(() => ({ data: null })),
        apiClient.get<BankAccount[]>('/banking/accounts').catch(() => ({ data: [] })),
        apiClient.get<BankTransaction[]>('/banking/transactions?limit=100').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/tenants/currencies').catch(() => ({ data: [] })),
      ]);

      setMetrics(metricsRes.data);
      setAccounts(accountsRes.data);
      setTransactions(txsRes.data);
      setCurrencies(currRes.data);

      if (accountsRes.data.length > 0 && !selectedAccForReconciliation) {
        setSelectedAccForReconciliation(accountsRes.data[0].id);
      }
    } catch (err) {
      console.error('Error fetching banking data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBankingData();
  }, []);

  // Fetch unreconciled transactions when selected account changes
  useEffect(() => {
    if (selectedAccForReconciliation) {
      apiClient
        .get<BankTransaction[]>(`/banking/transactions?bank_account_id=${selectedAccForReconciliation}&is_reconciled=false&limit=100`)
        .then((res) => {
          setUnreconciledTxs(res.data);
          setSelectedTxIds(new Set());
        })
        .catch(console.error);
    }
  }, [selectedAccForReconciliation]);

  const toggleSelectTx = (id: string) => {
    const updated = new Set(selectedTxIds);
    if (updated.has(id)) {
      updated.delete(id);
    } else {
      updated.add(id);
    }
    setSelectedTxIds(updated);
  };

  const handleSelectAllUnreconciled = () => {
    if (selectedTxIds.size === unreconciledTxs.length) {
      setSelectedTxIds(new Set());
    } else {
      setSelectedTxIds(new Set(unreconciledTxs.map((t) => t.id)));
    }
  };

  const handleConfirmReconciliation = async () => {
    if (selectedTxIds.size === 0) {
      alert('Seleccione al menos un movimiento para conciliar.');
      return;
    }

    setReconciling(true);
    try {
      const res = await apiClient.post('/banking/reconcile', {
        bank_account_id: selectedAccForReconciliation,
        transaction_ids: Array.from(selectedTxIds),
      });

      alert(`¡Se conciliaron ${res.data.reconciled_count} movimientos exitosamente!`);
      await fetchBankingData();
      // Reload unreconciled list
      const txRes = await apiClient.get<BankTransaction[]>(
        `/banking/transactions?bank_account_id=${selectedAccForReconciliation}&is_reconciled=false&limit=100`
      );
      setUnreconciledTxs(txRes.data);
      setSelectedTxIds(new Set());
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al conciliar movimientos bancarios.');
    } finally {
      setReconciling(false);
    }
  };

  const handleExecuteTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceAccId || !targetAccId || sourceAccId === targetAccId) {
      alert('Seleccione cuentas origen y destino distintas.');
      return;
    }
    if (transferAmount <= 0) {
      alert('Ingrese un monto válido a transferir.');
      return;
    }

    setSubmittingTransfer(true);
    try {
      await apiClient.post('/banking/transfers', {
        source_account_id: sourceAccId,
        target_account_id: targetAccId,
        amount: Number(transferAmount),
        operation_number: transferOpNum,
        notes: transferNotes,
      });

      alert('¡Transferencia interbancaria ejecutada exitosamente!');
      setShowTransferModal(false);
      setTransferAmount(0);
      setTransferOpNum('');
      setTransferNotes('');
      await fetchBankingData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al ejecutar la transferencia.');
    } finally {
      setSubmittingTransfer(false);
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBankName || !newAccNumber || !newClabe || !newCurrencyId) {
      alert('Complete todos los campos requeridos.');
      return;
    }

    setSubmittingAccount(true);
    try {
      await apiClient.post('/banking/accounts', {
        bank_name: newBankName,
        account_number: newAccNumber,
        clabe: newClabe,
        currency_id: newCurrencyId,
        initial_balance: Number(newInitialBalance) || 0,
      });

      alert('¡Cuenta bancaria creada exitosamente!');
      setShowNewAccountModal(false);
      setNewBankName('');
      setNewAccNumber('');
      setNewClabe('');
      setNewInitialBalance(0);
      await fetchBankingData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al crear la cuenta bancaria.');
    } finally {
      setSubmittingAccount(false);
    }
  };

  // Calculations for selected unreconciled transactions
  const selectedTxsArray = unreconciledTxs.filter((t) => selectedTxIds.has(t.id));
  const selectedInSum = selectedTxsArray.filter((t) => t.direction === 'IN').reduce((acc, t) => acc + Number(t.amount), 0);
  const selectedOutSum = selectedTxsArray.filter((t) => t.direction === 'OUT').reduce((acc, t) => acc + Number(t.amount), 0);
  const selectedNetImpact = selectedInSum - selectedOutSum;

  const currentAccount = accounts.find((a) => a.id === selectedAccForReconciliation);

  return (
    <div className="space-y-6">
      {/* Title & Top Action Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 bg-emerald-600 text-white rounded-xl shadow-md shadow-emerald-500/20">
              <Landmark className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
              Bancos y Tesorería
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Libro mayor de transacciones inmutables, control de sobregiro y conciliación bancaria.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowTransferModal(true)}
            className="inline-flex items-center px-4 py-2 bg-slate-900 hover:bg-black text-white rounded-xl text-xs font-bold shadow-sm transition-colors"
          >
            <ArrowLeftRight className="w-4 h-4 mr-1.5" /> Transferencia Entre Cuentas
          </button>

          <button
            onClick={() => setShowNewAccountModal(true)}
            className="inline-flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-sm transition-colors"
          >
            <PlusCircle className="w-4 h-4 mr-1.5" /> Nueva Cuenta Bancaria
          </button>

          <button
            onClick={fetchBankingData}
            disabled={loading}
            className="p-2 bg-white border border-slate-200 text-slate-600 hover:text-emerald-600 rounded-xl text-xs font-semibold shadow-2xs hover:bg-slate-50 transition-colors"
            title="Actualizar datos"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs Header */}
      <div className="flex border-b border-slate-200 space-x-2 overflow-x-auto pb-px">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'dashboard'
              ? 'border-emerald-600 text-emerald-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Dashboard de Tesorería</span>
        </button>

        <button
          onClick={() => setActiveTab('reconciliation')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'reconciliation'
              ? 'border-emerald-600 text-emerald-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Scale className="w-4 h-4" />
          <span>Conciliación Bancaria (Doble Panel)</span>
        </button>
      </div>

      {/* TAB 1: DASHBOARD DE TESORERÍA */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Header KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Saldo Contable Total</p>
                <h3 className="text-2xl font-extrabold text-slate-900 mt-1">
                  ${(metrics?.total_book_balance || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-emerald-600 flex items-center mt-1">
                  <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Saldo en libros ERP
                </span>
              </div>
              <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center">
                <Wallet className="w-6 h-6" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Saldo Conciliado Total</p>
                <h3 className="text-2xl font-extrabold text-blue-600 mt-1">
                  ${(metrics?.total_reconciled_balance || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-blue-700 flex items-center mt-1">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Cotejado con bancos
                </span>
              </div>
              <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Ingresos del Mes</p>
                <h3 className="text-2xl font-extrabold text-emerald-600 mt-1">
                  +${(metrics?.monthly_inflow || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-emerald-700 flex items-center mt-1">
                  <TrendingUp className="w-3.5 h-3.5 mr-1" /> Cobranza y depósitos
                </span>
              </div>
              <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center">
                <TrendingUp className="w-6 h-6" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Egresos del Mes</p>
                <h3 className="text-2xl font-extrabold text-rose-600 mt-1">
                  -${(metrics?.monthly_outflow || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </h3>
                <span className="text-xs font-medium text-rose-700 flex items-center mt-1">
                  <TrendingDown className="w-3.5 h-3.5 mr-1" /> Pagos a proveedores
                </span>
              </div>
              <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-xl flex items-center justify-center">
                <TrendingDown className="w-6 h-6" />
              </div>
            </div>
          </div>

          {/* Bank Accounts Cards */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900 flex items-center">
                <Landmark className="w-4 h-4 mr-2 text-emerald-600" /> Cuentas Bancarias Activas ({accounts.length})
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {accounts.map((acc) => (
                <div key={acc.id} className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm relative overflow-hidden">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <span className="text-xs font-bold text-slate-900 block">{acc.bank_name}</span>
                      <span className="text-[11px] text-slate-400 font-mono">No. {acc.account_number}</span>
                    </div>
                    <span className="text-xs font-extrabold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded">
                      {acc.currency_code}
                    </span>
                  </div>

                  <div className="space-y-1 mb-4">
                    <p className="text-[11px] text-slate-500">CLABE: {acc.clabe}</p>
                    <div className="flex justify-between items-baseline pt-2 border-t border-slate-50">
                      <span className="text-xs font-semibold text-slate-500">Saldo Contable:</span>
                      <span className="text-lg font-extrabold text-slate-900">
                        ${acc.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs font-semibold text-slate-400">Saldo Conciliado:</span>
                      <span className="text-xs font-bold text-blue-600">
                        ${acc.reconciled_balance.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setSelectedAccForReconciliation(acc.id);
                      setActiveTab('reconciliation');
                    }}
                    className="w-full py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl text-xs font-bold flex items-center justify-center space-x-1 transition-colors"
                  >
                    <Scale className="w-3.5 h-3.5 mr-1" /> Conciliar Movimientos
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Bank Transactions Table */}
          <div className="bg-white rounded-2xl p-6 border border-slate-100 shadow-sm">
            <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center">
              <Clock className="w-4 h-4 mr-2 text-blue-600" /> Libro Mayor de Bancos (Últimos Movimientos)
            </h4>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                  <tr>
                    <th className="py-2.5 px-3">Fecha</th>
                    <th className="py-2.5 px-3">Banco / Cuenta</th>
                    <th className="py-2.5 px-3">Tipo Movimiento</th>
                    <th className="py-2.5 px-3">Referencia / Folio</th>
                    <th className="py-2.5 px-3 text-right">Monto</th>
                    <th className="py-2.5 px-3 text-right">Saldo Resultante</th>
                    <th className="py-2.5 px-3 text-center">Conciliado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {transactions.length > 0 ? (
                    transactions.map((t) => (
                      <tr key={t.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="py-3 px-3 text-slate-500">
                          {new Date(t.transaction_date).toLocaleDateString('es-MX')} {new Date(t.transaction_date).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="py-3 px-3 font-semibold text-slate-800">
                          {t.bank_name} {t.account_number ? `(${t.account_number})` : ''}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded font-bold text-[11px] ${
                              t.direction === 'IN'
                                ? 'bg-emerald-50 text-emerald-700'
                                : 'bg-rose-50 text-rose-700'
                            }`}
                          >
                            {t.transaction_type}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-slate-600 font-medium">
                          {t.reference_folio || t.operation_number || t.reference_type}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-extrabold ${
                            t.direction === 'IN' ? 'text-emerald-600' : 'text-rose-600'
                          }`}
                        >
                          {t.direction === 'IN' ? '+' : '-'}${Number(t.amount).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-3 text-right font-bold text-slate-900">
                          ${Number(t.new_balance).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-3 text-center">
                          {t.is_reconciled ? (
                            <span className="inline-flex items-center text-xs font-bold text-emerald-600">
                              <CheckCircle2 className="w-4 h-4 mr-1" /> Sí
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">Pendiente</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        No hay movimientos registrados en el libro mayor de bancos.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CONCILIACIÓN BANCARIA (DOBLE PANEL) */}
      {activeTab === 'reconciliation' && (
        <div className="space-y-6">
          {/* Account Selector */}
          <div className="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center space-x-3 w-full sm:w-auto">
              <span className="text-xs font-bold text-slate-700 whitespace-nowrap">Cuenta a Conciliar:</span>
              <select
                value={selectedAccForReconciliation}
                onChange={(e) => setSelectedAccForReconciliation(e.target.value)}
                className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-800 focus:ring-2 focus:ring-emerald-500/20"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.bank_name} - Cuenta {a.account_number} (Contable: ${a.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })})
                  </option>
                ))}
              </select>
            </div>

            {currentAccount && (
              <div className="flex items-center space-x-6 text-xs">
                <div>
                  <span className="text-slate-400 block">Saldo Contable:</span>
                  <span className="font-extrabold text-slate-900 text-sm">
                    ${currentAccount.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Saldo Conciliado:</span>
                  <span className="font-extrabold text-blue-600 text-sm">
                    ${currentAccount.reconciled_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Diferencia por Conciliar:</span>
                  <span className="font-extrabold text-amber-600 text-sm">
                    ${(currentAccount.current_balance - currentAccount.reconciled_balance).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Two-Panel Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Panel: Unreconciled System Transactions (2 Columns) */}
            <div className="lg:col-span-2 bg-white rounded-2xl p-5 border border-slate-100 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={unreconciledTxs.length > 0 && selectedTxIds.size === unreconciledTxs.length}
                    onChange={handleSelectAllUnreconciled}
                    className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Movimientos Pendientes de Conciliación ({unreconciledTxs.length})
                  </h4>
                </div>
                <span className="text-[11px] text-slate-400">Seleccione los cotejados en su extracto bancario</span>
              </div>

              <div className="max-h-[500px] overflow-y-auto divide-y divide-slate-100">
                {unreconciledTxs.length > 0 ? (
                  unreconciledTxs.map((tx) => {
                    const isSelected = selectedTxIds.has(tx.id);
                    return (
                      <div
                        key={tx.id}
                        onClick={() => toggleSelectTx(tx.id)}
                        className={`p-3 rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                          isSelected ? 'bg-emerald-50/70 border border-emerald-200' : 'hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}} // handled by parent div
                            className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 pointer-events-none"
                          />
                          <div>
                            <p className="font-bold text-xs text-slate-900">
                              {tx.transaction_type} • {tx.reference_folio || tx.operation_number || 'S/R'}
                            </p>
                            <p className="text-[11px] text-slate-500">
                              {new Date(tx.transaction_date).toLocaleDateString('es-MX')} • {tx.notes || 'Sin observaciones'}
                            </p>
                          </div>
                        </div>

                        <div className="text-right">
                          <span
                            className={`font-extrabold text-xs block ${
                              tx.direction === 'IN' ? 'text-emerald-600' : 'text-rose-600'
                            }`}
                          >
                            {tx.direction === 'IN' ? '+' : '-'}${Number(tx.amount).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                          </span>
                          <span className="text-[10px] text-slate-400 font-medium">{tx.direction}</span>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <p className="py-12 text-center text-xs text-slate-400">
                    ¡Todos los movimientos de esta cuenta están conciliados!
                  </p>
                )}
              </div>
            </div>

            {/* Right Panel: Reconciliation Summary & Batch Action */}
            <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm space-y-5 h-fit">
              <div>
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-1">
                  Resumen de Cotejo Bancario
                </h4>
                <p className="text-[11px] text-slate-500">
                  Total de movimientos seleccionados para aprobar en el extracto oficial.
                </p>
              </div>

              <div className="bg-slate-50 p-4 rounded-xl space-y-3 text-xs">
                <div className="flex justify-between items-center text-slate-600">
                  <span>Partidas Seleccionadas:</span>
                  <span className="font-bold text-slate-900">{selectedTxIds.size}</span>
                </div>
                <div className="flex justify-between items-center text-slate-600">
                  <span>Depósitos / Ingresos (+):</span>
                  <span className="font-bold text-emerald-600">+${selectedInSum.toLocaleString('es-MX', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between items-center text-slate-600">
                  <span>Retiros / Pagos (-):</span>
                  <span className="font-bold text-rose-600">-${selectedOutSum.toLocaleString('es-MX', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-slate-200 font-extrabold text-sm text-slate-900">
                  <span>Impacto Neto Conciliado:</span>
                  <span className={selectedNetImpact >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                    {selectedNetImpact >= 0 ? '+' : ''}${selectedNetImpact.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              <button
                onClick={handleConfirmReconciliation}
                disabled={reconciling || selectedTxIds.size === 0}
                className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-md shadow-emerald-500/20 flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{reconciling ? 'Conciliando...' : `Aprobar y Conciliar (${selectedTxIds.size}) Movimientos`}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Interbank Transfer */}
      {showTransferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-3xl shadow-xl max-w-lg w-full p-6 animate-in fade-in">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-5">
              <div>
                <h3 className="text-base font-extrabold text-slate-900">Transferencia Entre Cuentas</h3>
                <p className="text-xs text-slate-500">Traspaso de fondos entre cuentas de la empresa.</p>
              </div>
              <button
                onClick={() => setShowTransferModal(false)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleExecuteTransfer} className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Cuenta Bancaria Origen (Retiro) *</label>
                <select
                  required
                  value={sourceAccId}
                  onChange={(e) => setSourceAccId(e.target.value)}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl"
                >
                  <option value="">Seleccione cuenta origen...</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.bank_name} - {a.account_number} (Disponible: ${a.current_balance.toLocaleString('es-MX', { minimumFractionDigits: 2 })})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Cuenta Bancaria Destino (Depósito) *</label>
                <select
                  required
                  value={targetAccId}
                  onChange={(e) => setTargetAccId(e.target.value)}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl"
                >
                  <option value="">Seleccione cuenta destino...</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.bank_name} - {a.account_number}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Monto a Transferir ($) *</label>
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  required
                  value={transferAmount}
                  onChange={(e) => setTransferAmount(Number(e.target.value))}
                  placeholder="0.00"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-right font-bold text-sm"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Clave de Rastreo SPEI / Referencia</label>
                <input
                  type="text"
                  value={transferOpNum}
                  onChange={(e) => setTransferOpNum(e.target.value)}
                  placeholder="Ej: SPEI-00123984"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Notas / Concepto</label>
                <input
                  type="text"
                  value={transferNotes}
                  onChange={(e) => setTransferNotes(e.target.value)}
                  placeholder="Traspaso para nómina / proveedores..."
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowTransferModal(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl font-bold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingTransfer}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold disabled:opacity-50"
                >
                  {submittingTransfer ? 'Transfiriendo...' : 'Ejecutar Transferencia'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: New Bank Account */}
      {showNewAccountModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-3xl shadow-xl max-w-lg w-full p-6 animate-in fade-in">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-5">
              <div>
                <h3 className="text-base font-extrabold text-slate-900">Nueva Cuenta Bancaria</h3>
                <p className="text-xs text-slate-500">Alta de chequera o cuenta de cheques en tesorería.</p>
              </div>
              <button
                onClick={() => setShowNewAccountModal(false)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Institución Bancaria *</label>
                <input
                  type="text"
                  required
                  value={newBankName}
                  onChange={(e) => setNewBankName(e.target.value)}
                  placeholder="BBVA, Santander, Banorte, CitiBanamex..."
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Número de Cuenta *</label>
                <input
                  type="text"
                  required
                  value={newAccNumber}
                  onChange={(e) => setNewAccNumber(e.target.value)}
                  placeholder="10 dígitos de la cuenta..."
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-mono"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">CLABE Interbancaria (18 dígitos) *</label>
                <input
                  type="text"
                  required
                  maxLength={18}
                  value={newClabe}
                  onChange={(e) => setNewClabe(e.target.value)}
                  placeholder="012180001234567890"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-mono"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Moneda *</label>
                <select
                  required
                  value={newCurrencyId}
                  onChange={(e) => setNewCurrencyId(e.target.value)}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium"
                >
                  <option value="">Seleccione moneda...</option>
                  {currencies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code} - {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Saldo Inicial de Apertura ($)</label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={newInitialBalance}
                  onChange={(e) => setNewInitialBalance(Number(e.target.value))}
                  placeholder="0.00"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-right font-bold text-sm"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowNewAccountModal(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl font-bold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingAccount}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold disabled:opacity-50"
                >
                  {submittingAccount ? 'Guardando...' : 'Crear Cuenta'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

