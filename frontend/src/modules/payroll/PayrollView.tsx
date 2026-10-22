import React, { useState, useEffect } from 'react';
import {
  Users,
  DollarSign,
  Calendar,
  FileText,
  Send,
  CheckCircle,
  AlertTriangle,
  ShieldCheck,
  Download,
  Plus,
  Search,
  Building,
  RefreshCw,
  Eye,
  Table,
  Landmark,
  FileSpreadsheet,
  Percent,
  TrendingUp,
  UserCheck,
  X,
  CreditCard
} from 'lucide-react';
import {
  Employee,
  PayrollPeriod,
  PayrollReceipt,
  PayrollDashboardMetrics,
  PrenominaGridRow,
  BankAccount
} from './types';

export const PayrollView: React.FC = () => {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'dashboard' | 'periods' | 'prenomina' | 'employees'>('dashboard');

  // State
  const [metrics, setMetrics] = useState<PayrollDashboardMetrics | null>(null);
  const [periods, setPeriods] = useState<PayrollPeriod[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<PayrollPeriod | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Prenómina Grid State
  const [prenominaGrid, setPrenominaGrid] = useState<PrenominaGridRow[]>([]);

  // Modals
  const [showNewPeriodModal, setShowNewPeriodModal] = useState<boolean>(false);
  const [showNewEmployeeModal, setShowNewEmployeeModal] = useState<boolean>(false);
  const [showDisburseModal, setShowDisburseModal] = useState<boolean>(false);
  const [selectedDisburseBank, setSelectedDisburseBank] = useState<string>('');
  const [isProcessingDisburse, setIsProcessingDisburse] = useState<boolean>(false);
  const [isBatchStamping, setIsBatchStamping] = useState<boolean>(false);

  // Kiosk Receipt Viewer Modal
  const [viewingReceipt, setViewingReceipt] = useState<PayrollReceipt | null>(null);

  // New Period Form
  const [periodForm, setPeriodForm] = useState({
    name: '1ra Quincena Octubre 2026',
    payroll_type: 'O',
    periodicity: '04',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date(Date.now() + 14 * 86400000).toISOString().split('T')[0],
    payment_date: new Date(Date.now() + 14 * 86400000).toISOString().split('T')[0],
    days_paid: 15.0
  });

  // New Employee Form
  const [empForm, setEmpForm] = useState({
    code: '',
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    rfc: '',
    curp: '',
    nss: '',
    zip_code: '06000',
    hire_date: new Date().toISOString().split('T')[0],
    daily_salary: 500,
    integrated_daily_salary: 524.5,
    contract_type: '01',
    work_shift_type: '01',
    regime_type: '02',
    risk_class: '1',
    periodicity: '04',
    department: 'Operaciones',
    job_title: 'Especialista',
    bank_name: 'BBVA México',
    bank_account_number: '012180001234567890',
    status: 'ACTIVO' as const
  });

  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const loadData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Dashboard
      const dashRes = await fetch('http://127.0.0.1:8000/api/v1/payroll/dashboard', { headers });
      if (dashRes.ok) {
        const d = await dashRes.json();
        setMetrics(d);
      }

      // 2. Periods
      const perRes = await fetch('http://127.0.0.1:8000/api/v1/payroll/periods', { headers });
      if (perRes.ok) {
        const pList = await perRes.json();
        setPeriods(pList);
        if (pList.length > 0 && !selectedPeriod) {
          loadPeriodDetail(pList[0].id);
        }
      }

      // 3. Employees
      const empRes = await fetch('http://127.0.0.1:8000/api/v1/payroll/employees', { headers });
      if (empRes.ok) {
        const emps: Employee[] = await empRes.json();
        setEmployees(emps);
      }

      // 4. Bank Accounts for disbursement
      const bankRes = await fetch('http://127.0.0.1:8000/api/v1/banking/accounts', { headers });
      if (bankRes.ok) {
        const bList = await bankRes.json();
        setBankAccounts(bList);
        if (bList.length > 0 && !selectedDisburseBank) {
          setSelectedDisburseBank(bList[0].id);
        }
      }
    } catch (err: any) {
      setErrorMsg('Error al conectar con el servidor de nómina: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadPeriodDetail = async (periodId: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/payroll/periods/${periodId}`, { headers });
      if (res.ok) {
        const detailedPeriod: PayrollPeriod = await res.json();
        setSelectedPeriod(detailedPeriod);

        // Populate prenomina interactive grid
        if (employees.length > 0) {
          buildPrenominaGrid(detailedPeriod, employees);
        }
      }
    } catch (e: any) {
      setErrorMsg('Error cargando detalle del periodo: ' + e.message);
    }
  };

  const buildPrenominaGrid = (period: PayrollPeriod, empList: Employee[]) => {
    const incMap = new Map<string, any[]>();
    (period.incidents || []).forEach(inc => {
      const current = incMap.get(inc.employee_id) || [];
      current.push(inc);
      incMap.set(inc.employee_id, current);
    });

    const rows: PrenominaGridRow[] = empList.filter(e => e.status === 'ACTIVO').map(e => {
      const incs = incMap.get(e.id) || [];
      let faltas = 0;
      let incaps = 0;
      let hDobles = 0;
      let hTriples = 0;
      let bonos = 0;
      let comisiones = 0;

      incs.forEach(inc => {
        if (inc.incident_type === 'FALTA_INJUSTIFICADA') faltas += Number(inc.quantity);
        if (inc.incident_type === 'INCAPACIDAD') incaps += Number(inc.quantity);
        if (inc.incident_type === 'HORAS_EXTRAS_DOBLES') hDobles += Number(inc.quantity);
        if (inc.incident_type === 'HORAS_EXTRAS_TRIPLES') hTriples += Number(inc.quantity);
        if (inc.incident_type === 'BONO') bonos += Number(inc.amount);
        if (inc.incident_type === 'COMISION') comisiones += Number(inc.amount);
      });

      return {
        employee_id: e.id,
        code: e.code,
        name: `${e.first_name} ${e.last_name}`,
        daily_salary: e.daily_salary,
        integrated_daily_salary: e.integrated_daily_salary,
        faltas_dias: faltas,
        incapacidades_dias: incaps,
        horas_dobles: hDobles,
        horas_triples: hTriples,
        bonos: bonos,
        comisiones: comisiones
      };
    });

    setPrenominaGrid(rows);
  };

  useEffect(() => {
    if (selectedPeriod && employees.length > 0) {
      buildPrenominaGrid(selectedPeriod, employees);
    }
  }, [employees]);

  // Handle Prenómina Grid Input Changes
  const handleGridChange = (employeeId: string, field: keyof PrenominaGridRow, val: number) => {
    setPrenominaGrid(prev =>
      prev.map(row => (row.employee_id === employeeId ? { ...row, [field]: Math.max(0, val) } : row))
    );
  };

  // Save Prenómina Matrix
  const handleSavePrenomina = async () => {
    if (!selectedPeriod) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const payload = {
        payroll_period_id: selectedPeriod.id,
        rows: prenominaGrid.map(r => ({
          employee_id: r.employee_id,
          faltas_dias: r.faltas_dias,
          incapacidades_dias: r.incapacidades_dias,
          horas_dobles: r.horas_dobles,
          horas_triples: r.horas_triples,
          bonos: r.bonos,
          comisiones: r.comisiones
        }))
      };

      const res = await fetch('http://127.0.0.1:8000/api/v1/payroll/prenomina/bulk', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al guardar prenómina');
      }

      setSuccessMsg('Incidencias de prenómina guardadas correctamente. Calculando nómina...');
      await handleCalculatePayroll();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  // Calculate Payroll
  const handleCalculatePayroll = async () => {
    if (!selectedPeriod) return;
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/payroll/periods/${selectedPeriod.id}/calculate`, {
        method: 'POST',
        headers
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al calcular nómina');
      }
      setSuccessMsg('Nómina calculada exitosamente conforme a LISR e IMSS.');
      await loadPeriodDetail(selectedPeriod.id);
      loadData();
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  // Create Period
  const handleCreatePeriod = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/payroll/periods', {
        method: 'POST',
        headers,
        body: JSON.stringify(periodForm)
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al crear periodo');
      }
      const newPer = await res.json();
      setShowNewPeriodModal(false);
      setSuccessMsg(`Periodo ${newPer.folio} creado.`);
      await loadData();
      loadPeriodDetail(newPer.id);
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  // Create Employee
  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/payroll/employees', {
        method: 'POST',
        headers,
        body: JSON.stringify(empForm)
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al dar de alta empleado');
      }
      setShowNewEmployeeModal(false);
      setSuccessMsg(`Empleado ${empForm.first_name} registrado.`);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  // Disburse Payroll (Atomic Bank Withdrawal)
  const handleDisbursePayroll = async () => {
    if (!selectedPeriod || !selectedDisburseBank) return;
    setIsProcessingDisburse(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/payroll/periods/${selectedPeriod.id}/disburse`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ bank_account_id: selectedDisburseBank })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al dispersar nómina');
      }
      const result = await res.json();
      setShowDisburseModal(false);
      setSuccessMsg(
        `Dispersión completada con éxito. Débito bancario: $${Number(result.disbursed_net_amount).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
      );
      await loadPeriodDetail(selectedPeriod.id);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setIsProcessingDisburse(false);
    }
  };

  // Batch Stamping
  const handleBatchStamp = async () => {
    if (!selectedPeriod) return;
    setIsBatchStamping(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/payroll/periods/${selectedPeriod.id}/stamp-batch`, {
        method: 'POST',
        headers
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error durante el timbrado en lote');
      }
      const stampRes = await res.json();
      setSuccessMsg(
        `Timbrado en Lote finalizado: ${stampRes.stamped_count} recibos certificados con CFDI 1.2 del SAT.`
      );
      await loadPeriodDetail(selectedPeriod.id);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setIsBatchStamping(false);
    }
  };

  const formatCurrency = (val: number | undefined) => {
    return (val || 0).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Module Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 bg-blue-600/20 border border-blue-500/30 rounded-xl flex items-center justify-center text-blue-400">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Nómina y Recursos Humanos</h1>
            <p className="text-slate-400 text-sm">
              Cálculo de ISR (Art. 96), Cuotas Obreras IMSS, Prenómina rápida, CFDI 1.2 y Dispersión Bancaria
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowNewPeriodModal(true)}
            className="flex items-center space-x-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Nuevo Periodo</span>
          </button>
          <button
            onClick={() => setShowNewEmployeeModal(true)}
            className="flex items-center space-x-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition-all"
          >
            <UserCheck className="w-4 h-4" />
            <span>Alta Empleado</span>
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

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-800 space-x-2">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'dashboard'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>Dashboard RRHH</span>
        </button>

        <button
          onClick={() => setActiveTab('periods')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'periods'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Periodos y Recibos</span>
          {periods.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[11px] text-slate-300">
              {periods.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('prenomina')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'prenomina'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" />
          <span>Prenómina (Grid Rápido)</span>
        </button>

        <button
          onClick={() => setActiveTab('employees')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'employees'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Expediente del Personal</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[11px] text-slate-300">
            {employees.length}
          </span>
        </button>
      </div>

      {/* ==================================================== */}
      {/* TAB 1: DASHBOARD RRHH */}
      {/* ==================================================== */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Executive KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Costo Total Nómina</p>
                  <p className="text-2xl font-bold text-white mt-1">
                    {formatCurrency(metrics?.total_payroll_cost_month)}
                  </p>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400 border border-blue-500/20">
                  <DollarSign className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3 flex items-center space-x-1">
                <span>Percepciones Brutas + Carga Patronal</span>
              </p>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Headcount Activo</p>
                  <p className="text-2xl font-bold text-emerald-400 mt-1">
                    {metrics?.total_active_employees || 0} Trabajadores
                  </p>
                </div>
                <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
                  <UserCheck className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Personal activo registrado ante IMSS</p>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Seguridad Social (IMSS)</p>
                  <p className="text-2xl font-bold text-amber-400 mt-1">
                    {formatCurrency(metrics?.total_social_security_imss)}
                  </p>
                </div>
                <div className="p-3 bg-amber-500/10 rounded-xl text-amber-400 border border-amber-500/20">
                  <ShieldCheck className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Cuotas obrero-patronales consolidadas</p>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sueldo Neto Dispersado</p>
                  <p className="text-2xl font-bold text-purple-400 mt-1">
                    {formatCurrency(metrics?.total_net_salary_disbursed)}
                  </p>
                </div>
                <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400 border border-purple-500/20">
                  <Landmark className="w-5 h-5" />
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">Líquido pagado en cuentas bancarias</p>
            </div>
          </div>

          {/* Social Burden Comparison Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 mb-6">
              <div>
                <h3 className="text-lg font-semibold text-white">Análisis de Carga Social (IMSS / Infonavit) vs Sueldo Neto</h3>
                <p className="text-xs text-slate-400">Proporción de costo de seguridad social frente al ingreso neto del trabajador</p>
              </div>
              <div className="mt-2 md:mt-0 flex items-center space-x-2 text-sm bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-700">
                <Percent className="w-4 h-4 text-amber-400" />
                <span className="text-slate-300 font-medium">Factor Carga Social:</span>
                <span className="text-amber-400 font-bold">{metrics?.social_burden_percentage || 0}%</span>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>Sueldo Neto Pagado a Trabajadores</span>
                  <span className="text-purple-400 font-semibold">{formatCurrency(metrics?.total_net_salary_disbursed)}</span>
                </div>
                <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full"
                    style={{ width: `${Math.min(100, Math.max(10, 100 - (metrics?.social_burden_percentage || 25)))}%` }}
                  ></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>Carga de Seguridad Social (IMSS Obrero + Patronal)</span>
                  <span className="text-amber-400 font-semibold">{formatCurrency(metrics?.total_social_security_imss)}</span>
                </div>
                <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 rounded-full"
                    style={{ width: `${Math.min(100, metrics?.social_burden_percentage || 25)}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* TAB 2: PERIODOS Y RECIBOS */}
      {/* ==================================================== */}
      {activeTab === 'periods' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Period List */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-semibold text-white text-sm">Periodos de Nómina</h3>
              <button
                onClick={() => setShowNewPeriodModal(true)}
                className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center space-x-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Nuevo</span>
              </button>
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
              {periods.map(p => {
                const isSelected = selectedPeriod?.id === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => loadPeriodDetail(p.id)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-blue-600/10 border-blue-500/50 shadow-md shadow-blue-500/5'
                        : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="text-xs font-mono font-bold text-blue-400">{p.folio}</span>
                        <p className="text-sm font-semibold text-white leading-tight mt-0.5">{p.name}</p>
                      </div>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          p.status === 'TIMBRADA'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : p.status === 'DISPERSADA'
                            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                            : p.status === 'CALCULADA'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {p.status}
                      </span>
                    </div>

                    <div className="flex items-center justify-between mt-3 text-xs text-slate-400 pt-2 border-t border-slate-800/50">
                      <span>{p.start_date} al {p.end_date}</span>
                      <span className="font-semibold text-white">{formatCurrency(p.total_net)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Period Detail & Receipts */}
          <div className="lg:col-span-2 space-y-6">
            {selectedPeriod ? (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
                {/* Period Actions Bar */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">
                        {selectedPeriod.folio}
                      </span>
                      <h2 className="text-lg font-bold text-white">{selectedPeriod.name}</h2>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Periodicidad: {selectedPeriod.periodicity === '04' ? 'Quincenal' : 'Semanal'} | {selectedPeriod.days_paid} días pagados | Fecha de Pago: {selectedPeriod.payment_date}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={handleCalculatePayroll}
                      className="flex items-center space-x-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition-all"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Recalcular</span>
                    </button>

                    <button
                      onClick={() => setShowDisburseModal(true)}
                      disabled={selectedPeriod.status === 'DISPERSADA' || selectedPeriod.total_net <= 0}
                      className="flex items-center space-x-1.5 px-3.5 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all shadow-lg shadow-purple-600/20"
                    >
                      <CreditCard className="w-3.5 h-3.5" />
                      <span>{selectedPeriod.status === 'DISPERSADA' ? 'Dispersada' : 'Dispersar Banco'}</span>
                    </button>

                    <button
                      onClick={handleBatchStamp}
                      disabled={isBatchStamping || selectedPeriod.status === 'TIMBRADA'}
                      className="flex items-center space-x-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all shadow-lg shadow-emerald-600/20"
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>{isBatchStamping ? 'Timbrando...' : 'Timbrar en Lote CFDI'}</span>
                    </button>
                  </div>
                </div>

                {/* Period Summary Numbers */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                    <p className="text-[11px] text-slate-400 uppercase font-semibold">Percepciones</p>
                    <p className="text-lg font-bold text-white mt-0.5">{formatCurrency(selectedPeriod.total_perceptions)}</p>
                  </div>
                  <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                    <p className="text-[11px] text-slate-400 uppercase font-semibold">Retención ISR</p>
                    <p className="text-lg font-bold text-red-400 mt-0.5">{formatCurrency(selectedPeriod.total_isr_retention)}</p>
                  </div>
                  <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                    <p className="text-[11px] text-slate-400 uppercase font-semibold">IMSS Obrero</p>
                    <p className="text-lg font-bold text-amber-400 mt-0.5">{formatCurrency(selectedPeriod.total_imss_employee)}</p>
                  </div>
                  <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                    <p className="text-[11px] text-slate-400 uppercase font-semibold">Neto a Pagar</p>
                    <p className="text-lg font-bold text-emerald-400 mt-0.5">{formatCurrency(selectedPeriod.total_net)}</p>
                  </div>
                </div>

                {/* Receipts Table */}
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-white">Recibos de Nómina ({selectedPeriod.receipts?.length || 0})</h4>
                  <div className="overflow-x-auto border border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
                        <tr>
                          <th className="py-3 px-3">Folio</th>
                          <th className="py-3 px-3">Trabajador</th>
                          <th className="py-3 px-3">Días</th>
                          <th className="py-3 px-3">Percepciones</th>
                          <th className="py-3 px-3">Deducciones</th>
                          <th className="py-3 px-3">Neto</th>
                          <th className="py-3 px-3">Estado</th>
                          <th className="py-3 px-3 text-center">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {selectedPeriod.receipts?.map(rec => (
                          <tr key={rec.id} className="hover:bg-slate-800/40 transition-colors">
                            <td className="py-2.5 px-3 font-mono font-medium text-blue-400">{rec.folio}</td>
                            <td className="py-2.5 px-3">
                              <p className="font-semibold text-white">{rec.employee_name}</p>
                              <p className="text-[10px] text-slate-400 font-mono">{rec.employee_rfc}</p>
                            </td>
                            <td className="py-2.5 px-3">{rec.days_paid}</td>
                            <td className="py-2.5 px-3">{formatCurrency(rec.total_perceptions)}</td>
                            <td className="py-2.5 px-3 text-red-300">{formatCurrency(rec.total_deductions)}</td>
                            <td className="py-2.5 px-3 font-bold text-emerald-400">{formatCurrency(rec.total_net)}</td>
                            <td className="py-2.5 px-3">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  rec.status === 'TIMBRADO'
                                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                    : 'bg-slate-800 text-slate-300'
                                }`}
                              >
                                {rec.status}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <button
                                onClick={() => setViewingReceipt(rec)}
                                className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
                                title="Ver Recibo Desglosado (Kiosco)"
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
              </div>
            ) : (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
                <Calendar className="w-12 h-12 mx-auto text-slate-600 mb-3" />
                <p>Selecciona un periodo de la lista izquierda para visualizar y gestionar sus recibos.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* TAB 3: PRENÓMINA (MATRIZ INTERACTIVA GRID) */}
      {/* ==================================================== */}
      {activeTab === 'prenomina' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center space-x-2">
                <FileSpreadsheet className="w-5 h-5 text-blue-400" />
                <span>Matriz de Captura Rápida de Prenómina (Grid Excel)</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Periodo Activo: {selectedPeriod ? `${selectedPeriod.folio} - ${selectedPeriod.name}` : 'Ninguno seleccionado'}
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={handleSavePrenomina}
                disabled={!selectedPeriod || selectedPeriod.status === 'DISPERSADA'}
                className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all"
              >
                <CheckCircle className="w-4 h-4" />
                <span>Guardar y Recalcular</span>
              </button>
            </div>
          </div>

          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/90 text-slate-400 uppercase font-semibold border-b border-slate-800 select-none">
                <tr>
                  <th className="py-3 px-3">Clave</th>
                  <th className="py-3 px-3">Trabajador</th>
                  <th className="py-3 px-3">Salario Diario (SD)</th>
                  <th className="py-3 px-3 bg-red-950/20 border-l border-r border-red-900/30 text-red-300">
                    Faltas (Días)
                  </th>
                  <th className="py-3 px-3 bg-amber-950/20 border-r border-amber-900/30 text-amber-300">
                    Incapacidad (Días)
                  </th>
                  <th className="py-3 px-3 bg-blue-950/20 border-r border-blue-900/30 text-blue-300">
                    Hrs Extra Dobles
                  </th>
                  <th className="py-3 px-3 bg-blue-950/20 border-r border-blue-900/30 text-blue-300">
                    Hrs Extra Triples
                  </th>
                  <th className="py-3 px-3 bg-emerald-950/20 border-r border-emerald-900/30 text-emerald-300">
                    Bonos ($)
                  </th>
                  <th className="py-3 px-3 bg-emerald-950/20 text-emerald-300">
                    Comisiones ($)
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {prenominaGrid.map(row => (
                  <tr key={row.employee_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-medium text-blue-400">{row.code}</td>
                    <td className="py-2.5 px-3 font-semibold text-white whitespace-nowrap">{row.name}</td>
                    <td className="py-2.5 px-3 font-mono">{formatCurrency(row.daily_salary)}</td>

                    {/* Faltas */}
                    <td className="py-2 px-2 bg-red-950/10 border-l border-r border-red-900/20">
                      <input
                        type="number"
                        min="0"
                        max="15"
                        step="1"
                        value={row.faltas_dias}
                        onChange={e => handleGridChange(row.employee_id, 'faltas_dias', parseFloat(e.target.value) || 0)}
                        className="w-20 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-center text-red-300 font-bold focus:border-red-500 focus:outline-none"
                      />
                    </td>

                    {/* Incapacidades */}
                    <td className="py-2 px-2 bg-amber-950/10 border-r border-amber-900/20">
                      <input
                        type="number"
                        min="0"
                        max="15"
                        step="1"
                        value={row.incapacidades_dias}
                        onChange={e =>
                          handleGridChange(row.employee_id, 'incapacidades_dias', parseFloat(e.target.value) || 0)
                        }
                        className="w-20 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-center text-amber-300 font-bold focus:border-amber-500 focus:outline-none"
                      />
                    </td>

                    {/* Horas Extras Dobles */}
                    <td className="py-2 px-2 bg-blue-950/10 border-r border-blue-900/20">
                      <input
                        type="number"
                        min="0"
                        max="50"
                        step="1"
                        value={row.horas_dobles}
                        onChange={e => handleGridChange(row.employee_id, 'horas_dobles', parseFloat(e.target.value) || 0)}
                        className="w-20 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-center text-blue-300 font-bold focus:border-blue-500 focus:outline-none"
                      />
                    </td>

                    {/* Horas Extras Triples */}
                    <td className="py-2 px-2 bg-blue-950/10 border-r border-blue-900/20">
                      <input
                        type="number"
                        min="0"
                        max="50"
                        step="1"
                        value={row.horas_triples}
                        onChange={e => handleGridChange(row.employee_id, 'horas_triples', parseFloat(e.target.value) || 0)}
                        className="w-20 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-center text-blue-300 font-bold focus:border-blue-500 focus:outline-none"
                      />
                    </td>

                    {/* Bonos */}
                    <td className="py-2 px-2 bg-emerald-950/10 border-r border-emerald-900/20">
                      <input
                        type="number"
                        min="0"
                        step="50"
                        value={row.bonos}
                        onChange={e => handleGridChange(row.employee_id, 'bonos', parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-right text-emerald-300 font-bold focus:border-emerald-500 focus:outline-none"
                      />
                    </td>

                    {/* Comisiones */}
                    <td className="py-2 px-2 bg-emerald-950/10">
                      <input
                        type="number"
                        min="0"
                        step="50"
                        value={row.comisiones}
                        onChange={e => handleGridChange(row.employee_id, 'comisiones', parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-right text-emerald-300 font-bold focus:border-emerald-500 focus:outline-none"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* TAB 4: EXPEDIENTE DEL PERSONAL */}
      {/* ==================================================== */}
      {activeTab === 'employees' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-lg font-bold text-white">Catálogo Maestro de Trabajadores</h3>
              <p className="text-xs text-slate-400">Expediente laboral con RFC, CURP, NSS, Salario Diario y SDI vigentes</p>
            </div>
            <button
              onClick={() => setShowNewEmployeeModal(true)}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-blue-500/20"
            >
              <Plus className="w-4 h-4" />
              <span>Alta de Empleado</span>
            </button>
          </div>

          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-3 px-3">Clave</th>
                  <th className="py-3 px-3">Nombre Completo</th>
                  <th className="py-3 px-3">RFC</th>
                  <th className="py-3 px-3">CURP</th>
                  <th className="py-3 px-3">NSS</th>
                  <th className="py-3 px-3">Salario Diario</th>
                  <th className="py-3 px-3">SDI (IMSS)</th>
                  <th className="py-3 px-3">Departamento</th>
                  <th className="py-3 px-3">Puesto</th>
                  <th className="py-3 px-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {employees.map(emp => (
                  <tr key={emp.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-blue-400">{emp.code}</td>
                    <td className="py-2.5 px-3 font-semibold text-white whitespace-nowrap">
                      {emp.first_name} {emp.last_name}
                    </td>
                    <td className="py-2.5 px-3 font-mono">{emp.rfc}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px]">{emp.curp}</td>
                    <td className="py-2.5 px-3 font-mono">{emp.nss}</td>
                    <td className="py-2.5 px-3 font-bold text-white">{formatCurrency(emp.daily_salary)}</td>
                    <td className="py-2.5 px-3 font-bold text-amber-300">{formatCurrency(emp.integrated_daily_salary)}</td>
                    <td className="py-2.5 px-3">{emp.department}</td>
                    <td className="py-2.5 px-3 text-slate-400">{emp.job_title}</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        {emp.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* MODAL: VISOR DE RECIBO (KIOSCO) */}
      {/* ==================================================== */}
      {viewingReceipt && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-4xl w-full p-6 space-y-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex justify-between items-start pb-4 border-b border-slate-800">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Comprobante Fiscal Digital de Nómina (CFDI 1.2)</h3>
                  <p className="text-xs text-slate-400">Folio: {viewingReceipt.folio} | SAT Anexo 20</p>
                </div>
              </div>
              <button onClick={() => setViewingReceipt(null)} className="text-slate-400 hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Worker & Fiscal Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-950/70 border border-slate-800 rounded-2xl text-xs">
              <div>
                <span className="text-slate-500 uppercase block font-semibold">Trabajador</span>
                <span className="font-bold text-white block mt-0.5">{viewingReceipt.employee_name}</span>
                <span className="font-mono text-slate-400">{viewingReceipt.employee_rfc}</span>
              </div>
              <div>
                <span className="text-slate-500 uppercase block font-semibold">Días Laborados</span>
                <span className="font-bold text-white block mt-0.5">{viewingReceipt.days_paid} Días</span>
                <span className="text-slate-400">Salario Diario: {formatCurrency(viewingReceipt.daily_salary)}</span>
              </div>
              <div>
                <span className="text-slate-500 uppercase block font-semibold">SDI (IMSS)</span>
                <span className="font-bold text-amber-400 block mt-0.5">{formatCurrency(viewingReceipt.integrated_daily_salary)}</span>
                <span className="text-slate-400">Base Cotización</span>
              </div>
              <div>
                <span className="text-slate-500 uppercase block font-semibold">UUID Fiscal SAT</span>
                <span className="font-mono text-[11px] text-blue-400 block mt-0.5 truncate" title={viewingReceipt.cfdi_uuid || 'Sin timbrar'}>
                  {viewingReceipt.cfdi_uuid || 'Pendiente de Timbrado'}
                </span>
                <span className="text-emerald-400 font-semibold">{viewingReceipt.status}</span>
              </div>
            </div>

            {/* Perceptions (Left) vs Deductions (Right) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left: Percepciones */}
              <div className="bg-slate-950/50 border border-slate-800 rounded-2xl p-4 space-y-3">
                <div className="flex justify-between items-center pb-2 border-b border-slate-800 text-xs font-bold text-emerald-400 uppercase">
                  <span>Percepciones (Ingresos)</span>
                  <span>Importe</span>
                </div>
                <div className="space-y-2 text-xs">
                  {viewingReceipt.items
                    ?.filter(it => it.item_type === 'PERCEPCION')
                    .map(it => (
                      <div key={it.id} className="flex justify-between items-center py-1 border-b border-slate-800/40">
                        <div>
                          <p className="font-semibold text-white">{it.description}</p>
                          <p className="text-[10px] text-slate-500 font-mono">SAT {it.sat_code} | Clave: {it.concept_key}</p>
                        </div>
                        <span className="font-bold text-emerald-300 font-mono">{formatCurrency(it.total_amount)}</span>
                      </div>
                    ))}
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-slate-800 font-bold text-sm">
                  <span className="text-slate-300">Total Percepciones</span>
                  <span className="text-emerald-400">{formatCurrency(viewingReceipt.total_perceptions)}</span>
                </div>
              </div>

              {/* Right: Deducciones */}
              <div className="bg-slate-950/50 border border-slate-800 rounded-2xl p-4 space-y-3">
                <div className="flex justify-between items-center pb-2 border-b border-slate-800 text-xs font-bold text-red-400 uppercase">
                  <span>Deducciones (Retenciones)</span>
                  <span>Importe</span>
                </div>
                <div className="space-y-2 text-xs">
                  {viewingReceipt.items
                    ?.filter(it => it.item_type === 'DEDUCCION')
                    .map(it => (
                      <div key={it.id} className="flex justify-between items-center py-1 border-b border-slate-800/40">
                        <div>
                          <p className="font-semibold text-white">{it.description}</p>
                          <p className="text-[10px] text-slate-500 font-mono">SAT {it.sat_code} | Clave: {it.concept_key}</p>
                        </div>
                        <span className="font-bold text-red-300 font-mono">{formatCurrency(it.total_amount)}</span>
                      </div>
                    ))}
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-slate-800 font-bold text-sm">
                  <span className="text-slate-300">Total Deducciones</span>
                  <span className="text-red-400">{formatCurrency(viewingReceipt.total_deductions)}</span>
                </div>
              </div>
            </div>

            {/* Net Amount Highlight Card */}
            <div className="p-4 bg-emerald-950/30 border border-emerald-500/30 rounded-2xl flex items-center justify-between">
              <div>
                <p className="text-xs uppercase font-semibold text-emerald-400">Neto Efectivo a Recibir</p>
                <p className="text-xs text-slate-400">Monto depositado en cuenta bancaria del trabajador</p>
              </div>
              <p className="text-2xl font-black text-emerald-300 font-mono">{formatCurrency(viewingReceipt.total_net)}</p>
            </div>

            {/* XML CFDI Download & Close */}
            <div className="flex justify-end space-x-3 pt-2">
              {viewingReceipt.xml_cfdi && (
                <button
                  onClick={() => {
                    const blob = new Blob([viewingReceipt.xml_cfdi!], { type: 'text/xml' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `Nomina_${viewingReceipt.folio}.xml`;
                    a.click();
                  }}
                  className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold"
                >
                  <Download className="w-4 h-4 text-blue-400" />
                  <span>Descargar XML CFDI 4.0</span>
                </button>
              )}
              <button
                onClick={() => setViewingReceipt(null)}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold"
              >
                Cerrar Visor
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* MODAL: DISPERSIÓN BANCARIA PATRONAL */}
      {/* ==================================================== */}
      {showDisburseModal && selectedPeriod && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex justify-between items-start pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
                  <Landmark className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Dispersión de Nómina Patronal</h3>
                  <p className="text-xs text-slate-400">Retiro atómico y control de sobregiro</p>
                </div>
              </div>
              <button onClick={() => setShowDisburseModal(false)} className="text-slate-400 hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 bg-purple-950/20 border border-purple-800/40 rounded-2xl text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-400">Periodo a Liquidar:</span>
                <span className="text-white font-bold">{selectedPeriod.folio} - {selectedPeriod.name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-300 font-semibold">Total Líquido Requerido:</span>
                <span className="text-purple-300 font-bold">{formatCurrency(selectedPeriod.total_net)}</span>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300">Seleccionar Cuenta Bancaria Patronal</label>
              <select
                value={selectedDisburseBank}
                onChange={e => setSelectedDisburseBank(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-purple-500"
              >
                {bankAccounts.map(b => (
                  <option key={b.id} value={b.id}>
                    {b.bank_name} - {b.account_number} (Saldo Disp: {formatCurrency(b.current_balance)})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end space-x-3 pt-3">
              <button
                onClick={() => setShowDisburseModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </button>
              <button
                onClick={handleDisbursePayroll}
                disabled={isProcessingDisburse}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-purple-600/30 flex items-center space-x-2"
              >
                <CreditCard className="w-4 h-4" />
                <span>{isProcessingDisburse ? 'Procesando débito...' : 'Confirmar Dispersión'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* MODAL: NUEVO PERIODO */}
      {/* ==================================================== */}
      {showNewPeriodModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex justify-between items-start pb-3 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Nuevo Periodo de Nómina</h3>
              <button onClick={() => setShowNewPeriodModal(false)} className="text-slate-400 hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreatePeriod} className="space-y-4 text-xs">
              <div>
                <label className="text-slate-300 font-semibold block mb-1">Nombre Descriptivo</label>
                <input
                  type="text"
                  required
                  value={periodForm.name}
                  onChange={e => setPeriodForm({ ...periodForm, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Tipo Nómina SAT</label>
                  <select
                    value={periodForm.payroll_type}
                    onChange={e => setPeriodForm({ ...periodForm, payroll_type: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="O">O - Ordinaria</option>
                    <option value="E">E - Extraordinaria</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Periodicidad</label>
                  <select
                    value={periodForm.periodicity}
                    onChange={e => setPeriodForm({ ...periodForm, periodicity: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="04">04 - Quincenal</option>
                    <option value="02">02 - Semanal</option>
                    <option value="05">05 - Mensual</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Fecha Inicio</label>
                  <input
                    type="date"
                    required
                    value={periodForm.start_date}
                    onChange={e => setPeriodForm({ ...periodForm, start_date: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Fecha Fin</label>
                  <input
                    type="date"
                    required
                    value={periodForm.end_date}
                    onChange={e => setPeriodForm({ ...periodForm, end_date: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Días Pagados</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    required
                    value={periodForm.days_paid}
                    onChange={e => setPeriodForm({ ...periodForm, days_paid: parseFloat(e.target.value) || 15 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-2 text-white"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNewPeriodModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold"
                >
                  Crear Periodo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* MODAL: ALTA DE EMPLEADO */}
      {/* ==================================================== */}
      {showNewEmployeeModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 space-y-5 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start pb-3 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Alta de Trabajador en Nómina</h3>
              <button onClick={() => setShowNewEmployeeModal(false)} className="text-slate-400 hover:text-white p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateEmployee} className="space-y-4 text-xs">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Clave Empleado</label>
                  <input
                    type="text"
                    required
                    placeholder="EMP-004"
                    value={empForm.code}
                    onChange={e => setEmpForm({ ...empForm, code: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Nombre(s)</label>
                  <input
                    type="text"
                    required
                    placeholder="Roberto"
                    value={empForm.first_name}
                    onChange={e => setEmpForm({ ...empForm, first_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Apellidos</label>
                  <input
                    type="text"
                    required
                    placeholder="García Soto"
                    value={empForm.last_name}
                    onChange={e => setEmpForm({ ...empForm, last_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">RFC</label>
                  <input
                    type="text"
                    required
                    maxLength={13}
                    placeholder="GASR880214XYZ"
                    value={empForm.rfc}
                    onChange={e => setEmpForm({ ...empForm, rfc: e.target.value.toUpperCase() })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">CURP</label>
                  <input
                    type="text"
                    required
                    maxLength={18}
                    placeholder="GASR880214HDFRN01"
                    value={empForm.curp}
                    onChange={e => setEmpForm({ ...empForm, curp: e.target.value.toUpperCase() })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">NSS (IMSS)</label>
                  <input
                    type="text"
                    required
                    maxLength={11}
                    placeholder="12345678901"
                    value={empForm.nss}
                    onChange={e => setEmpForm({ ...empForm, nss: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Salario Diario (SD)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={empForm.daily_salary}
                    onChange={e =>
                      setEmpForm({
                        ...empForm,
                        daily_salary: parseFloat(e.target.value) || 0,
                        integrated_daily_salary: (parseFloat(e.target.value) || 0) * 1.0493
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-bold"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">SDI (IMSS Cotización)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={empForm.integrated_daily_salary}
                    onChange={e => setEmpForm({ ...empForm, integrated_daily_salary: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-amber-300 font-bold"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Riesgo Puesto IMSS</label>
                  <select
                    value={empForm.risk_class}
                    onChange={e => setEmpForm({ ...empForm, risk_class: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="1">Clase I (Mínimo)</option>
                    <option value="2">Clase II (Bajo)</option>
                    <option value="3">Clase III (Medio)</option>
                    <option value="4">Clase IV (Alto)</option>
                    <option value="5">Clase V (Máximo)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Departamento</label>
                  <input
                    type="text"
                    value={empForm.department}
                    onChange={e => setEmpForm({ ...empForm, department: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Puesto</label>
                  <input
                    type="text"
                    value={empForm.job_title}
                    onChange={e => setEmpForm({ ...empForm, job_title: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">CLABE / Cuenta Bancaria</label>
                  <input
                    type="text"
                    placeholder="012180001234567890"
                    value={empForm.bank_account_number}
                    onChange={e => setEmpForm({ ...empForm, bank_account_number: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNewEmployeeModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold"
                >
                  Guardar Trabajador
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
