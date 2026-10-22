import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BookOpen,
  DollarSign,
  TrendingUp,
  Scale,
  FileText,
  Plus,
  Search,
  CheckCircle,
  AlertTriangle,
  X,
  Eye,
  RefreshCw,
  Printer,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Building,
  Layers,
  ArrowRight,
  PieChart,
  Percent,
  Download,
  Filter
} from 'lucide-react';
import {
  Account,
  JournalEntry,
  JournalEntryLine,
  TrialBalanceReport,
  IncomeStatementReport,
  BalanceSheetReport,
  AccountingDashboardMetrics
} from './types';

export const AccountingView: React.FC = () => {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'dashboard' | 'entries' | 'reports' | 'chart'>('dashboard');
  const [activeReport, setActiveReport] = useState<'pnl' | 'balance' | 'trial'>('pnl');

  // State
  const [metrics, setMetrics] = useState<AccountingDashboardMetrics | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);

  // Financial Reports State
  const [pnlReport, setPnlReport] = useState<IncomeStatementReport | null>(null);
  const [bsReport, setBsReport] = useState<BalanceSheetReport | null>(null);
  const [trialReport, setTrialReport] = useState<TrialBalanceReport | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [entryTypeFilter, setEntryTypeFilter] = useState<string>('');
  const [moduleFilter, setModuleFilter] = useState<string>('');
  const [accountTypeFilter, setAccountTypeFilter] = useState<string>('');

  // New Journal Entry Modal State
  const [showNewEntryModal, setShowNewEntryModal] = useState<boolean>(false);
  const [newEntryHeader, setNewEntryHeader] = useState({
    entry_type: 'DIARIO',
    entry_date: new Date().toISOString().split('T')[0],
    concept: ''
  });
  const [newEntryLines, setNewEntryLines] = useState<
    Array<{ account_id: string; concept: string; debit: number; credit: number; cfdi_uuid?: string }>
  >([
    { account_id: '', concept: '', debit: 0, credit: 0 },
    { account_id: '', concept: '', debit: 0, credit: 0 }
  ]);

  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const loadData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. CFO Dashboard
      const dashRes = await fetch('http://127.0.0.1:8000/api/v1/accounting/dashboard', { headers });
      if (dashRes.ok) {
        const d = await dashRes.json();
        setMetrics(d);
      }

      // 2. Accounts
      const accRes = await fetch('http://127.0.0.1:8000/api/v1/accounting/accounts', { headers });
      if (accRes.ok) {
        const accs = await accRes.json();
        setAccounts(accs);
      }

      // 3. Entries
      const entRes = await fetch('http://127.0.0.1:8000/api/v1/accounting/journal-entries', { headers });
      if (entRes.ok) {
        const ents = await entRes.json();
        setEntries(ents);
      }

      // 4. Reports
      await loadReports();
    } catch (err: any) {
      setErrorMsg('Error al conectar con el servidor contable: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadReports = async () => {
    try {
      const today = new Date().toISOString().split('T')[0];
      const startOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0];

      // P&L
      const pnlRes = await fetch(
        `http://127.0.0.1:8000/api/v1/accounting/reports/income-statement?start_date=${startOfMonth}&end_date=${today}`,
        { headers }
      );
      if (pnlRes.ok) setPnlReport(await pnlRes.json());

      // Balance Sheet
      const bsRes = await fetch(`http://127.0.0.1:8000/api/v1/accounting/reports/balance-sheet?as_of_date=${today}`, {
        headers
      });
      if (bsRes.ok) setBsReport(await bsRes.json());

      // Trial Balance
      const trialRes = await fetch(
        `http://127.0.0.1:8000/api/v1/accounting/reports/trial-balance?start_date=${startOfMonth}&end_date=${today}`,
        { headers }
      );
      if (trialRes.ok) setTrialReport(await trialRes.json());
    } catch (e: any) {
      console.error('Error cargando reportes financieros:', e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Journal Entry Real-Time Math
  const totalDebits = newEntryLines.reduce((acc, l) => acc + (Number(l.debit) || 0), 0);
  const totalCredits = newEntryLines.reduce((acc, l) => acc + (Number(l.credit) || 0), 0);
  const lineDiff = Math.abs(totalDebits - totalCredits);
  const isBalanced = lineDiff < 0.01 && totalDebits > 0;

  const handleLineChange = (index: number, field: string, value: any) => {
    const updated = [...newEntryLines];
    updated[index] = { ...updated[index], [field]: value };
    setNewEntryLines(updated);
  };

  const addLine = () => {
    setNewEntryLines([...newEntryLines, { account_id: '', concept: newEntryHeader.concept || '', debit: 0, credit: 0 }]);
  };

  const removeLine = (index: number) => {
    if (newEntryLines.length > 2) {
      setNewEntryLines(newEntryLines.filter((_, i) => i !== index));
    }
  };

  // Submit Manual Journal Entry
  const handleCreateEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isBalanced) {
      setErrorMsg(`La póliza no está cuadrada. Diferencia: $${lineDiff.toFixed(2)}`);
      return;
    }
    setErrorMsg(null);
    try {
      const payload = {
        entry_type: newEntryHeader.entry_type,
        entry_date: newEntryHeader.entry_date,
        concept: newEntryHeader.concept,
        lines: newEntryLines.map(l => ({
          account_id: l.account_id,
          concept: l.concept || newEntryHeader.concept,
          debit: Number(l.debit) || 0,
          credit: Number(l.credit) || 0,
          cfdi_uuid: l.cfdi_uuid || undefined
        }))
      };

      const res = await fetch('http://127.0.0.1:8000/api/v1/accounting/journal-entries', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al guardar la póliza');
      }

      const created = await res.json();
      setShowNewEntryModal(false);
      setSuccessMsg(`Póliza ${created.folio} creada y aplicada con éxito.`);
      setNewEntryLines([
        { account_id: '', concept: '', debit: 0, credit: 0 },
        { account_id: '', concept: '', debit: 0, credit: 0 }
      ]);
      setNewEntryHeader({ ...newEntryHeader, concept: '' });
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const formatCurrency = (val: number | undefined) => {
    return (val || 0).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
  };

  // Selectable non-group accounts for journal lines
  const selectableAccounts = accounts.filter(a => !a.is_group);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="p-6 max-w-7xl mx-auto space-y-6 font-sans"
    >
      {/* Module Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 bg-emerald-600/20 border border-emerald-500/30 rounded-xl flex items-center justify-center text-emerald-400">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Contabilidad y Estados Financieros</h1>
            <p className="text-slate-400 text-sm">
              Partida Doble Inquebrantable, Pólizas Automáticas en Tiempo Real, Balanza SAT y Balance General
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowNewEntryModal(true)}
            className="flex items-center space-x-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-emerald-500/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Nueva Póliza</span>
          </button>
          <button
            onClick={loadData}
            className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition-colors"
            title="Recargar Estados Financieros"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="flex items-center space-x-3 p-4 bg-red-950/50 border border-red-800/80 rounded-xl text-red-300 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="flex items-center space-x-3 p-4 bg-emerald-950/50 border border-emerald-800/80 rounded-xl text-emerald-300 text-sm">
          <CheckCircle className="w-5 h-5 flex-shrink-0 text-emerald-400" />
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 space-x-2">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'dashboard'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>Dashboard CFO</span>
        </button>

        <button
          onClick={() => setActiveTab('entries')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'entries'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          <span>Pólizas Contables</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[11px] text-slate-300">
            {entries.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('reports')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'reports'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Estados Financieros</span>
        </button>

        <button
          onClick={() => setActiveTab('chart')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'chart'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Catálogo de Cuentas (SAT)</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[11px] text-slate-300">
            {accounts.length}
          </span>
        </button>
      </div>

      {/* ==================================================== */}
      {/* TAB 1: CFO DASHBOARD */}
      {/* ==================================================== */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Executive KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Activo Total</p>
                  <p className="text-2xl font-bold text-white mt-1">
                    {formatCurrency(metrics?.total_assets)}
                  </p>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400 border border-blue-500/20">
                  <Building className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Bancos, Clientes e Inventarios</p>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Pasivo Total</p>
                  <p className="text-2xl font-bold text-red-400 mt-1">
                    {formatCurrency(metrics?.total_liabilities)}
                  </p>
                </div>
                <div className="p-3 bg-red-500/10 rounded-xl text-red-400 border border-red-500/20">
                  <DollarSign className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Proveedores e Impuestos por Pagar</p>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Utilidad Neta (Mes)</p>
                  <p className="text-2xl font-bold text-emerald-400 mt-1">
                    {formatCurrency(metrics?.monthly_net_income)}
                  </p>
                </div>
                <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
                  <TrendingUp className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Margen Bruto: {metrics?.gross_margin_percentage || 0}%</p>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Capital Contable</p>
                  <p className="text-2xl font-bold text-purple-400 mt-1">
                    {formatCurrency(metrics?.total_equity)}
                  </p>
                </div>
                <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400 border border-purple-500/20">
                  <Scale className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Patrimonio Neto de la Empresa</p>
            </div>
          </div>

          {/* Recent Pólizas */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="font-semibold text-white text-sm">Últimas Pólizas Contables Integradas</h3>
              <button
                onClick={() => setActiveTab('entries')}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-medium"
              >
                Ver Todas &rarr;
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/70 text-slate-400 uppercase font-semibold">
                  <tr>
                    <th className="py-2.5 px-3">Folio</th>
                    <th className="py-2.5 px-3">Tipo</th>
                    <th className="py-2.5 px-3">Fecha</th>
                    <th className="py-2.5 px-3">Concepto</th>
                    <th className="py-2.5 px-3">Módulo Origen</th>
                    <th className="py-2.5 px-3 text-right">Monto Cuadrado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {metrics?.recent_entries.map(ent => (
                    <tr key={ent.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-2 px-3 font-mono font-bold text-emerald-400">{ent.folio}</td>
                      <td className="py-2 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">
                          {ent.entry_type}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-400">{ent.entry_date}</td>
                      <td className="py-2 px-3 font-medium text-white">{ent.concept}</td>
                      <td className="py-2 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          {ent.source_module}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-white">
                        {formatCurrency(ent.total_debit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* TAB 2: PÓLIZAS CONTABLES */}
      {/* ==================================================== */}
      {activeTab === 'entries' && (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-2xl">
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={entryTypeFilter}
                onChange={e => setEntryTypeFilter(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white"
              >
                <option value="">Todos los Tipos</option>
                <option value="INGRESO">Pólizas de Ingreso</option>
                <option value="EGRESO">Pólizas de Egreso</option>
                <option value="DIARIO">Pólizas de Diario</option>
              </select>

              <select
                value={moduleFilter}
                onChange={e => setModuleFilter(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white"
              >
                <option value="">Todos los Orígenes</option>
                <option value="SALES">Ventas (Automáticas)</option>
                <option value="PURCHASES">Compras (Automáticas)</option>
                <option value="PAYROLL">Nómina (Automáticas)</option>
                <option value="CXP">Cuentas por Pagar</option>
                <option value="MANUAL">Pólizas Manuales</option>
              </select>
            </div>

            <button
              onClick={() => setShowNewEntryModal(true)}
              className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Capturar Póliza</span>
            </button>
          </div>

          {/* Journal Entries Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-3">Folio</th>
                  <th className="py-3 px-3">Tipo</th>
                  <th className="py-3 px-3">Fecha</th>
                  <th className="py-3 px-3">Concepto General</th>
                  <th className="py-3 px-3">Origen</th>
                  <th className="py-3 px-3 text-right">Cargos (Debe)</th>
                  <th className="py-3 px-3 text-right">Abonos (Haber)</th>
                  <th className="py-3 px-3 text-center">Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {entries
                  .filter(e => (!entryTypeFilter || e.entry_type === entryTypeFilter) && (!moduleFilter || e.source_module === moduleFilter))
                  .map(e => (
                    <tr key={e.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-emerald-400">{e.folio}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">
                          {e.entry_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{e.entry_date}</td>
                      <td className="py-2.5 px-3 font-medium text-white">{e.concept}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          {e.source_module} {e.source_folio ? `(${e.source_folio})` : ''}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-white">{formatCurrency(e.total_debit)}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-white">{formatCurrency(e.total_credit)}</td>
                      <td className="py-2.5 px-3 text-center">
                        <button
                          onClick={async () => {
                            const res = await fetch(`http://127.0.0.1:8000/api/v1/accounting/journal-entries/${e.id}`, { headers });
                            if (res.ok) setSelectedEntry(await res.json());
                          }}
                          className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
                          title="Ver Partidas de la Póliza"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* TAB 3: ESTADOS FINANCIEROS */}
      {/* ==================================================== */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          {/* Sub-Tabs for Reports */}
          <div className="flex border-b border-slate-800 space-x-3">
            <button
              onClick={() => setActiveReport('pnl')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl transition-all ${
                activeReport === 'pnl' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              Estado de Resultados (P&L)
            </button>
            <button
              onClick={() => setActiveReport('balance')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl transition-all ${
                activeReport === 'balance' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              Balance General
            </button>
            <button
              onClick={() => setActiveReport('trial')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl transition-all ${
                activeReport === 'trial' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              Balanza de Comprobación (SAT Anexo 24)
            </button>
          </div>

          {/* 1. ESTADO DE RESULTADOS */}
          {activeReport === 'pnl' && pnlReport && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
              <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                <div>
                  <h3 className="text-lg font-bold text-white">Estado de Resultados Integral</h3>
                  <p className="text-xs text-slate-400">
                    Periodo del {pnlReport.start_date} al {pnlReport.end_date} | Cifras en Moneda Nacional (MXN)
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 block font-semibold">Margen Bruto</span>
                  <span className="text-xl font-black text-emerald-400">{pnlReport.gross_margin_percentage}%</span>
                </div>
              </div>

              <div className="space-y-4 text-xs">
                {/* Ingresos */}
                <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex justify-between font-bold text-sm text-emerald-400">
                    <span>1. INGRESOS POR VENTAS NETAS</span>
                    <span>{formatCurrency(pnlReport.net_sales)}</span>
                  </div>
                  {pnlReport.revenue_lines.map((l, idx) => (
                    <div key={idx} className="flex justify-between text-slate-300 pl-4 py-0.5">
                      <span>{l.account_number} - {l.name}</span>
                      <span className="font-mono">{formatCurrency(l.amount)}</span>
                    </div>
                  ))}
                </div>

                {/* Costo de Ventas */}
                <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex justify-between font-bold text-sm text-red-300">
                    <span>2. MENOS: COSTO DE VENTAS (COGS)</span>
                    <span>({formatCurrency(pnlReport.cost_of_goods_sold)})</span>
                  </div>
                  {pnlReport.cogs_lines.map((l, idx) => (
                    <div key={idx} className="flex justify-between text-slate-300 pl-4 py-0.5">
                      <span>{l.account_number} - {l.name}</span>
                      <span className="font-mono">{formatCurrency(l.amount)}</span>
                    </div>
                  ))}
                </div>

                {/* Utilidad Bruta Highlight */}
                <div className="p-4 bg-blue-950/20 border border-blue-500/30 rounded-xl flex justify-between font-bold text-sm text-blue-300">
                  <span>(=) UTILIDAD BRUTA</span>
                  <span>{formatCurrency(pnlReport.gross_profit)}</span>
                </div>

                {/* Gastos de Operación */}
                <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex justify-between font-bold text-sm text-amber-300">
                    <span>3. MENOS: GASTOS DE OPERACIÓN (ADMINISTRACIÓN Y VENTAS)</span>
                    <span>({formatCurrency(pnlReport.operating_expenses)})</span>
                  </div>
                  {pnlReport.expense_lines.map((l, idx) => (
                    <div key={idx} className="flex justify-between text-slate-300 pl-4 py-0.5">
                      <span>{l.account_number} - {l.name}</span>
                      <span className="font-mono">{formatCurrency(l.amount)}</span>
                    </div>
                  ))}
                </div>

                {/* Utilidad Neta Highlight */}
                <div className="p-5 bg-emerald-950/40 border border-emerald-500/40 rounded-2xl flex justify-between items-center text-emerald-300">
                  <div>
                    <span className="text-sm font-bold block uppercase tracking-wider">(=) UTILIDAD NETA DEL EJERCICIO</span>
                    <span className="text-[11px] text-slate-400">Rendimiento contable final transferido a Capital Contable</span>
                  </div>
                  <span className="text-2xl font-black font-mono">{formatCurrency(pnlReport.net_income)}</span>
                </div>
              </div>
            </div>
          )}

          {/* 2. BALANCE GENERAL */}
          {activeReport === 'balance' && bsReport && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
              <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                <div>
                  <h3 className="text-lg font-bold text-white">Balance General (Estado de Situación Financiera)</h3>
                  <p className="text-xs text-slate-400">Al {bsReport.as_of_date} | Principio Contable Fundamental</p>
                </div>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold border ${
                    bsReport.is_balanced
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : 'bg-red-500/20 text-red-300 border-red-500/30'
                  }`}
                >
                  {bsReport.is_balanced ? 'Balance Cuadrado Exacto' : 'Descuadre en Balance'}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
                {/* Lado Izquierdo: ACTIVOS */}
                <div className="space-y-4">
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex justify-between font-bold text-sm text-blue-400">
                      <span>ACTIVO CIRCULANTE</span>
                      <span>{formatCurrency(bsReport.current_assets.total)}</span>
                    </div>
                    {bsReport.current_assets.lines.map((l, idx) => (
                      <div key={idx} className="flex justify-between text-slate-300 pl-3 py-0.5">
                        <span>{l.account_number} - {l.name}</span>
                        <span className="font-mono">{formatCurrency(l.amount)}</span>
                      </div>
                    ))}
                  </div>

                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex justify-between font-bold text-sm text-blue-300">
                      <span>ACTIVO NO CIRCULANTE (FIJO)</span>
                      <span>{formatCurrency(bsReport.non_current_assets.total)}</span>
                    </div>
                    {bsReport.non_current_assets.lines.map((l, idx) => (
                      <div key={idx} className="flex justify-between text-slate-300 pl-3 py-0.5">
                        <span>{l.account_number} - {l.name}</span>
                        <span className="font-mono">{formatCurrency(l.amount)}</span>
                      </div>
                    ))}
                  </div>

                  <div className="p-4 bg-blue-950/30 border border-blue-500/40 rounded-xl flex justify-between font-bold text-sm text-white">
                    <span>TOTAL ACTIVO</span>
                    <span>{formatCurrency(bsReport.total_assets)}</span>
                  </div>
                </div>

                {/* Lado Derecho: PASIVOS Y CAPITAL */}
                <div className="space-y-4">
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex justify-between font-bold text-sm text-red-400">
                      <span>PASIVO A CORTO PLAZO</span>
                      <span>{formatCurrency(bsReport.short_term_liabilities.total)}</span>
                    </div>
                    {bsReport.short_term_liabilities.lines.map((l, idx) => (
                      <div key={idx} className="flex justify-between text-slate-300 pl-3 py-0.5">
                        <span>{l.account_number} - {l.name}</span>
                        <span className="font-mono">{formatCurrency(l.amount)}</span>
                      </div>
                    ))}
                  </div>

                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex justify-between font-bold text-sm text-purple-400">
                      <span>CAPITAL CONTABLE</span>
                      <span>{formatCurrency(bsReport.total_equity)}</span>
                    </div>
                    {bsReport.equity.lines.map((l, idx) => (
                      <div key={idx} className="flex justify-between text-slate-300 pl-3 py-0.5">
                        <span>{l.account_number} - {l.name}</span>
                        <span className="font-mono">{formatCurrency(l.amount)}</span>
                      </div>
                    ))}
                    <div className="flex justify-between text-emerald-300 font-semibold pl-3 py-0.5">
                      <span>Utilidad Neta del Ejercicio</span>
                      <span className="font-mono">{formatCurrency(bsReport.current_year_net_income)}</span>
                    </div>
                  </div>

                  <div className="p-4 bg-purple-950/30 border border-purple-500/40 rounded-xl flex justify-between font-bold text-sm text-white">
                    <span>TOTAL PASIVO + CAPITAL</span>
                    <span>{formatCurrency(bsReport.total_liabilities_and_equity)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 3. BALANZA DE COMPROBACIÓN */}
          {activeReport === 'trial' && trialReport && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-slate-800">
                <div>
                  <h3 className="text-lg font-bold text-white">Balanza de Comprobación (Anexo 24 SAT)</h3>
                  <p className="text-xs text-slate-400">Sumas Iguales Verificadas para Contabilidad Electrónica</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  Sumas Iguales Cuadradas
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Cuenta</th>
                      <th className="py-2.5 px-3">Nombre</th>
                      <th className="py-2.5 px-3">Código SAT</th>
                      <th className="py-2.5 px-3 text-right">Cargos Periodo</th>
                      <th className="py-2.5 px-3 text-right">Abonos Periodo</th>
                      <th className="py-2.5 px-3 text-right">Saldo Final Debe</th>
                      <th className="py-2.5 px-3 text-right">Saldo Final Haber</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {trialReport.items.map((item, idx) => (
                      <tr
                        key={idx}
                        className={`${item.is_group ? 'bg-slate-950/40 font-bold text-white' : 'hover:bg-slate-800/40'}`}
                      >
                        <td className="py-2 px-3 font-mono">{item.account_number}</td>
                        <td className="py-2 px-3">{item.name}</td>
                        <td className="py-2 px-3 font-mono text-[11px] text-slate-400">{item.sat_group_code}</td>
                        <td className="py-2 px-3 text-right font-mono">{item.period_debit > 0 ? formatCurrency(item.period_debit) : '-'}</td>
                        <td className="py-2 px-3 text-right font-mono">{item.period_credit > 0 ? formatCurrency(item.period_credit) : '-'}</td>
                        <td className="py-2 px-3 text-right font-mono text-blue-300">{item.final_debit > 0 ? formatCurrency(item.final_debit) : '-'}</td>
                        <td className="py-2 px-3 text-right font-mono text-emerald-300">{item.final_credit > 0 ? formatCurrency(item.final_credit) : '-'}</td>
                      </tr>
                    ))}
                    {/* Sumas Iguales Row */}
                    <tr className="bg-emerald-950/40 font-bold text-emerald-300 text-sm border-t-2 border-emerald-500">
                      <td colSpan={3} className="py-3 px-3 uppercase">SUMAS TOTALES CUADRADAS</td>
                      <td className="py-3 px-3 text-right font-mono">{formatCurrency(trialReport.total_period_debit)}</td>
                      <td className="py-3 px-3 text-right font-mono">{formatCurrency(trialReport.total_period_credit)}</td>
                      <td className="py-3 px-3 text-right font-mono">{formatCurrency(trialReport.total_final_debit)}</td>
                      <td className="py-3 px-3 text-right font-mono">{formatCurrency(trialReport.total_final_credit)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================================================== */}
      {/* TAB 4: CATÁLOGO DE CUENTAS */}
      {/* ==================================================== */}
      {activeTab === 'chart' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-lg font-bold text-white">Catálogo de Cuentas Contables (Anexo 24 SAT)</h3>
              <p className="text-xs text-slate-400">Cuentas de Mayor y Subcuentas Imputables con Código Agrupador</p>
            </div>
            <div className="flex items-center space-x-3">
              <select
                value={accountTypeFilter}
                onChange={e => setAccountTypeFilter(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white"
              >
                <option value="">Todas las Naturalezas</option>
                <option value="ACTIVO">Activos (1000)</option>
                <option value="PASIVO">Pasivos (2000)</option>
                <option value="CAPITAL">Capital (3000)</option>
                <option value="INGRESOS">Ingresos (4000)</option>
                <option value="COSTOS">Costos (5000)</option>
                <option value="GASTOS">Gastos (6000)</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-3">Cuenta</th>
                  <th className="py-3 px-3">Descripción de la Cuenta</th>
                  <th className="py-3 px-3">Tipo</th>
                  <th className="py-3 px-3">Naturaleza</th>
                  <th className="py-3 px-3">Código SAT</th>
                  <th className="py-3 px-3 text-right">Saldo Actual</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {accounts
                  .filter(a => !accountTypeFilter || a.account_type === accountTypeFilter)
                  .map(acc => (
                    <tr
                      key={acc.id}
                      className={`${acc.is_group ? 'bg-slate-950/50 font-bold text-white' : 'hover:bg-slate-800/40'}`}
                    >
                      <td className="py-2.5 px-3 font-mono font-bold text-emerald-400">{acc.account_number}</td>
                      <td className="py-2.5 px-3" style={{ paddingLeft: `${(acc.level - 1) * 20 + 12}px` }}>
                        {acc.name}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">
                          {acc.account_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">{acc.nature}</td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-blue-400">{acc.sat_group_code}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-white">
                        {formatCurrency(acc.current_balance)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* MODAL: NUEVA PÓLIZA (GRID INTERACTIVO CON CUADRE EN TIEMPO REAL) */}
      {/* ==================================================== */}
      {showNewEntryModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-4xl w-full p-6 space-y-5 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <Scale className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Captura de Póliza Contable (Partida Doble)</h3>
                  <p className="text-xs text-slate-400">Validación de cuadre y trazabilidad fiscal en tiempo real</p>
                </div>
              </div>
              <button onClick={() => setShowNewEntryModal(false)} className="text-slate-400 hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateEntry} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Tipo de Póliza</label>
                  <select
                    value={newEntryHeader.entry_type}
                    onChange={e => setNewEntryHeader({ ...newEntryHeader, entry_type: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="DIARIO">Póliza de Diario</option>
                    <option value="INGRESO">Póliza de Ingreso</option>
                    <option value="EGRESO">Póliza de Egreso</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Fecha</label>
                  <input
                    type="date"
                    required
                    value={newEntryHeader.entry_date}
                    onChange={e => setNewEntryHeader({ ...newEntryHeader, entry_date: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Concepto General</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej: Registro de aportación de capital"
                    value={newEntryHeader.concept}
                    onChange={e => setNewEntryHeader({ ...newEntryHeader, concept: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
              </div>

              {/* Lines Grid Table */}
              <div className="border border-slate-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/90 text-slate-400 uppercase font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 w-48">Cuenta Contable</th>
                      <th className="py-2.5 px-3">Concepto Particular</th>
                      <th className="py-2.5 px-3 w-32 text-right">Cargo (Debe)</th>
                      <th className="py-2.5 px-3 w-32 text-right">Abono (Haber)</th>
                      <th className="py-2.5 px-3 w-10 text-center"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {newEntryLines.map((line, idx) => (
                      <tr key={idx} className="bg-slate-900/60">
                        <td className="py-2 px-2">
                          <select
                            required
                            value={line.account_id}
                            onChange={e => handleLineChange(idx, 'account_id', e.target.value)}
                            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-white font-mono text-[11px]"
                          >
                            <option value="">Seleccionar Cuenta...</option>
                            {selectableAccounts.map(a => (
                              <option key={a.id} value={a.id}>
                                {a.account_number} - {a.name}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="text"
                            placeholder="Concepto de la partida"
                            value={line.concept}
                            onChange={e => handleLineChange(idx, 'concept', e.target.value)}
                            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-white"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={line.debit}
                            onChange={e => handleLineChange(idx, 'debit', parseFloat(e.target.value) || 0)}
                            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-right text-blue-300 font-mono font-bold"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={line.credit}
                            onChange={e => handleLineChange(idx, 'credit', parseFloat(e.target.value) || 0)}
                            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-right text-emerald-300 font-mono font-bold"
                          />
                        </td>
                        <td className="py-2 px-2 text-center">
                          <button
                            type="button"
                            onClick={() => removeLine(idx)}
                            className="text-red-400 hover:text-red-300 p-1"
                            title="Eliminar partida"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-between items-center">
                <button
                  type="button"
                  onClick={addLine}
                  className="flex items-center space-x-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Agregar Partida</span>
                </button>

                {/* Real-time Balancing Banner */}
                <div
                  className={`flex items-center space-x-3 px-4 py-2 rounded-xl border text-xs font-bold ${
                    isBalanced
                      ? 'bg-emerald-950/50 text-emerald-300 border-emerald-500/40'
                      : 'bg-red-950/50 text-red-300 border-red-500/40'
                  }`}
                >
                  <span>Cargos: {formatCurrency(totalDebits)}</span>
                  <span>|</span>
                  <span>Abonos: {formatCurrency(totalCredits)}</span>
                  <span>|</span>
                  <span>
                    {isBalanced ? '✓ Póliza Cuadrada' : `Descuadre: ${formatCurrency(lineDiff)}`}
                  </span>
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNewEntryModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={!isBalanced}
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-600/30"
                >
                  Aplicar Póliza Contable
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* MODAL: VER DETALLE DE PÓLIZA */}
      {/* ==================================================== */}
      {selectedEntry && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-3xl w-full p-6 space-y-5 shadow-2xl">
            <div className="flex justify-between items-start pb-3 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                  {selectedEntry.folio}
                </span>
                <h3 className="text-lg font-bold text-white mt-1">{selectedEntry.concept}</h3>
                <p className="text-xs text-slate-400">
                  Fecha: {selectedEntry.entry_date} | Tipo: {selectedEntry.entry_type} | Origen: {selectedEntry.source_module}
                </p>
              </div>
              <button onClick={() => setSelectedEntry(null)} className="text-slate-400 hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="border border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Cuenta</th>
                    <th className="py-2.5 px-3">Concepto Particular</th>
                    <th className="py-2.5 px-3 text-right">Cargo (Debe)</th>
                    <th className="py-2.5 px-3 text-right">Abono (Haber)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {selectedEntry.lines?.map((l, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3">
                        <span className="font-mono font-bold text-emerald-400 block">{l.account_number}</span>
                        <span className="text-slate-400 text-[11px]">{l.account_name}</span>
                      </td>
                      <td className="py-2.5 px-3 font-medium text-white">{l.concept}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-blue-300">
                        {l.debit > 0 ? formatCurrency(l.debit) : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-300">
                        {l.credit > 0 ? formatCurrency(l.credit) : '-'}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-slate-950/70 font-bold text-white border-t border-slate-700">
                    <td colSpan={2} className="py-2.5 px-3 uppercase text-right">TOTALES CUADRADOS</td>
                    <td className="py-2.5 px-3 text-right font-mono text-blue-300">{formatCurrency(selectedEntry.total_debit)}</td>
                    <td className="py-2.5 px-3 text-right font-mono text-emerald-300">{formatCurrency(selectedEntry.total_credit)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedEntry(null)}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold"
              >
                Cerrar Póliza
              </button>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
};

