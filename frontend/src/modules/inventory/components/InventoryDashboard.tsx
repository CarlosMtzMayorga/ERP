import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence, Variants } from 'framer-motion';
import CountUp from 'react-countup';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import {
  TrendingUp,
  Package,
  ShoppingCart,
  DollarSign,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  Plus,
  Download,
  Filter,
  Search,
  Moon,
  Sun,
  Boxes,
  Layers,
  CheckCircle2,
  Clock,
  ArrowRightLeft,
  ChevronRight,
  MoreVertical,
  Activity,
} from 'lucide-react';

// ==========================================
// TYPES & DATA CONTRACTS
// ==========================================
export interface KPICardData {
  id: string;
  title: string;
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  changePercentage: number;
  changeType: 'positive' | 'negative' | 'neutral';
  comparisonText: string;
  icon: React.ElementType;
}

export interface InventoryTrendPoint {
  date: string;
  inventoryValue: number;
  inflow: number;
  outflow: number;
  ordersCount: number;
}

export interface CriticalProductItem {
  id: string;
  sku: string;
  name: string;
  category: string;
  currentStock: number;
  minThreshold: number;
  unitCost: number;
  totalValuation: number;
  location: string;
  status: 'critical' | 'warning' | 'optimal';
}

export interface CategoryDistribution {
  name: string;
  count: number;
  valuation: number;
  percentage: number;
}

// ==========================================
// MOCK DATA GENERATOR (ENTERPRISE GRADE)
// ==========================================
const MOCK_KPIS: KPICardData[] = [
  {
    id: 'kpi-revenue',
    title: 'Ingresos Totales',
    value: 1428950,
    prefix: '$',
    decimals: 2,
    changePercentage: 14.8,
    changeType: 'positive',
    comparisonText: 'vs. mes anterior',
    icon: DollarSign,
  },
  {
    id: 'kpi-orders',
    title: 'Órdenes Procesadas',
    value: 3842,
    suffix: ' pedidos',
    decimals: 0,
    changePercentage: 8.4,
    changeType: 'positive',
    comparisonText: 'vs. periodo previo',
    icon: ShoppingCart,
  },
  {
    id: 'kpi-valuation',
    title: 'Valor de Inventario',
    value: 894320,
    prefix: '$',
    decimals: 2,
    changePercentage: -2.3,
    changeType: 'negative',
    comparisonText: 'optimización de merma',
    icon: Package,
  },
  {
    id: 'kpi-alerts',
    title: 'Alertas de Stock',
    value: 12,
    suffix: ' ítems',
    decimals: 0,
    changePercentage: -18.5,
    changeType: 'positive',
    comparisonText: 'menos roturas de stock',
    icon: AlertTriangle,
  },
];

const MOCK_TIMEFRAME_DATA: Record<'7D' | '30D' | '90D' | '1Y', InventoryTrendPoint[]> = {
  '7D': [
    { date: '16 Oct', inventoryValue: 860000, inflow: 45000, outflow: 38000, ordersCount: 420 },
    { date: '17 Oct', inventoryValue: 867000, inflow: 52000, outflow: 45000, ordersCount: 480 },
    { date: '18 Oct', inventoryValue: 874000, inflow: 61000, outflow: 54000, ordersCount: 510 },
    { date: '19 Oct', inventoryValue: 881000, inflow: 48000, outflow: 41000, ordersCount: 460 },
    { date: '20 Oct', inventoryValue: 886000, inflow: 70000, outflow: 65000, ordersCount: 590 },
    { date: '21 Oct', inventoryValue: 891000, inflow: 55000, outflow: 50000, ordersCount: 530 },
    { date: '22 Oct', inventoryValue: 894320, inflow: 63000, outflow: 59680, ordersCount: 580 },
  ],
  '30D': [
    { date: 'Semana 1', inventoryValue: 820000, inflow: 180000, outflow: 160000, ordersCount: 1840 },
    { date: 'Semana 2', inventoryValue: 845000, inflow: 210000, outflow: 185000, ordersCount: 2100 },
    { date: 'Semana 3', inventoryValue: 870000, inflow: 195000, outflow: 170000, ordersCount: 1950 },
    { date: 'Semana 4', inventoryValue: 894320, inflow: 240000, outflow: 215680, ordersCount: 2350 },
  ],
  '90D': [
    { date: 'Agosto', inventoryValue: 780000, inflow: 720000, outflow: 650000, ordersCount: 6800 },
    { date: 'Septiembre', inventoryValue: 835000, inflow: 810000, outflow: 755000, ordersCount: 7600 },
    { date: 'Octubre', inventoryValue: 894320, inflow: 890000, outflow: 830680, ordersCount: 8200 },
  ],
  '1Y': [
    { date: 'Q1', inventoryValue: 690000, inflow: 2100000, outflow: 1950000, ordersCount: 18400 },
    { date: 'Q2', inventoryValue: 740000, inflow: 2350000, outflow: 2300000, ordersCount: 21500 },
    { date: 'Q3', inventoryValue: 810000, inflow: 2600000, outflow: 2530000, ordersCount: 24200 },
    { date: 'Q4 (Est.)', inventoryValue: 894320, inflow: 2900000, outflow: 2815680, ordersCount: 26800 },
  ],
};

const MOCK_CRITICAL_PRODUCTS: CriticalProductItem[] = [
  {
    id: 'prod-1',
    sku: 'REF-ALM-102',
    name: 'Válvula Reguladora de Presión Neumática 1/2"',
    category: 'Componentes Industriales',
    currentStock: 4,
    minThreshold: 15,
    unitCost: 1250.0,
    totalValuation: 5000.0,
    location: 'Almacén Central - Pasillo 3B',
    status: 'critical',
  },
  {
    id: 'prod-2',
    sku: 'MOT-IND-045',
    name: 'Motor Trifásico Asíncrono 2.5 HP 220/440V',
    category: 'Maquinaria & Fuerza',
    currentStock: 2,
    minThreshold: 8,
    unitCost: 6840.0,
    totalValuation: 13680.0,
    location: 'Almacén Norte - Estante G',
    status: 'critical',
  },
  {
    id: 'prod-3',
    sku: 'CAB-COB-708',
    name: 'Rollo Cable THW Calibre 10 Cobre 100m',
    category: 'Material Eléctrico',
    currentStock: 9,
    minThreshold: 20,
    unitCost: 890.0,
    totalValuation: 8010.0,
    location: 'Almacén Central - Pasillo 1A',
    status: 'warning',
  },
  {
    id: 'prod-4',
    sku: 'SEN-OPT-993',
    name: 'Sensor Fotoeléctrico Reflectivo PNP 24V',
    category: 'Automatización & Sensores',
    currentStock: 11,
    minThreshold: 25,
    unitCost: 450.0,
    totalValuation: 4950.0,
    location: 'Almacén Este - Gaveta 14',
    status: 'warning',
  },
  {
    id: 'prod-5',
    sku: 'ROD-SKF-620',
    name: 'Rodamiento de Bolas Rígido SKF 6205-2RS',
    category: 'Rodamientos & Transmisión',
    currentStock: 18,
    minThreshold: 15,
    unitCost: 185.0,
    totalValuation: 3330.0,
    location: 'Almacén Central - Pasillo 4C',
    status: 'optimal',
  },
];

const MOCK_CATEGORIES: CategoryDistribution[] = [
  { name: 'Componentes Industriales', count: 142, valuation: 324500, percentage: 36.3 },
  { name: 'Maquinaria & Fuerza', count: 48, valuation: 278900, percentage: 31.2 },
  { name: 'Automatización & Sensores', count: 96, valuation: 165420, percentage: 18.5 },
  { name: 'Material Eléctrico', count: 180, valuation: 89500, percentage: 10.0 },
  { name: 'Fijaciones & Consumibles', count: 320, valuation: 36000, percentage: 4.0 },
];

// ==========================================
// FRAMER MOTION VARIANTS (STAGGERED CASCADE)
// ==========================================
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.04,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.5,
      ease: 'easeOut',
    },
  },
};

// ==========================================
// RECHARTS CUSTOM TOOLTIP (SAAS STYLE)
// ==========================================
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    name: string;
    payload: InventoryTrendPoint;
  }>;
  label?: string;
  isDark: boolean;
}

const CustomChartTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label, isDark }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div
        className={`p-4 rounded-xl shadow-xl border text-xs font-sans transition-all backdrop-blur-md ${
          isDark
            ? 'bg-gray-800/95 border-gray-700 text-gray-100 shadow-black/40'
            : 'bg-white/95 border-gray-200 text-gray-800 shadow-slate-200/80'
        }`}
      >
        <p className="font-semibold text-sm mb-2 text-[#047857] flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5" />
          {label}
        </p>
        <div className="space-y-1.5 min-w-[190px]">
          <div className="flex justify-between items-center py-0.5 border-b border-gray-100 dark:border-gray-700/50">
            <span className="text-gray-500 dark:text-gray-400">Valuación Almacén:</span>
            <span className="font-bold text-gray-900 dark:text-white">
              ${data.inventoryValue.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex justify-between items-center py-0.5">
            <span className="text-gray-500 dark:text-gray-400">Entradas (Recepción):</span>
            <span className="font-semibold text-emerald-600 dark:text-emerald-400">
              +${data.inflow.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex justify-between items-center py-0.5">
            <span className="text-gray-500 dark:text-gray-400">Salidas (Despacho):</span>
            <span className="font-semibold text-rose-500 dark:text-rose-400">
              -${data.outflow.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex justify-between items-center pt-1 border-t border-gray-100 dark:border-gray-700/50 text-[11px]">
            <span className="text-gray-400">Órdenes atendidas:</span>
            <span className="font-mono text-gray-600 dark:text-gray-300 font-medium">
              {data.ordersCount} pedidos
            </span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

// ==========================================
// MAIN COMPONENT
// ==========================================
export const InventoryDashboard: React.FC = () => {
  // Theme Toggle: Defaults to Light, supports explicit Dark Mode
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const [selectedTimeframe, setSelectedTimeframe] = useState<'7D' | '30D' | '90D' | '1Y'>('30D');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'critical' | 'warning' | 'optimal'>('all');

  const chartData = useMemo(() => {
    return MOCK_TIMEFRAME_DATA[selectedTimeframe];
  }, [selectedTimeframe]);

  const filteredProducts = useMemo(() => {
    return MOCK_CRITICAL_PRODUCTS.filter((prod) => {
      const matchesSearch =
        prod.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prod.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prod.category.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || prod.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [searchTerm, statusFilter]);

  const toggleTheme = () => {
    setIsDarkMode((prev) => !prev);
  };

  return (
    <div
      className={`min-h-screen transition-colors duration-300 ${
        isDarkMode ? 'dark bg-gray-900 text-gray-100' : 'bg-gray-50 text-gray-900'
      } font-sans p-4 sm:p-6 lg:p-8 antialiased`}
    >
      <motion.div
        className="max-w-7xl mx-auto space-y-6"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* ========================================================= */}
        {/* TOP HEADER & CONTROLS                                    */}
        {/* ========================================================= */}
        <motion.div
          variants={itemVariants}
          className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2"
        >
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] flex items-center justify-center border border-[#047857]/20">
                <Boxes className="w-5 h-5 text-[#047857]" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
                  <span>Dashboard de Gestión de Inventario</span>
                  <span className="hidden sm:inline-block px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                    SaaS Enterprise
                  </span>
                </h1>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Monitoreo de Kardex inmutable en tiempo real, costeo PEPS/Promedio y trazabilidad
                  operativa.
                </p>
              </div>
            </div>
          </div>

          {/* Action Header Buttons */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Dark / Light Mode Switcher */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle Theme"
              className="p-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all shadow-sm cursor-pointer"
            >
              {isDarkMode ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-gray-600" />
              )}
            </button>

            {/* Secondary Action */}
            <button className="flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 shadow-sm transition-all cursor-pointer">
              <Download className="w-4 h-4 text-gray-500 dark:text-gray-400" />
              <span>Exportar Kardex</span>
            </button>

            {/* Primary Action in Emerald Green (#047857) */}
            <button className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-xl bg-[#047857] hover:bg-emerald-800 text-white shadow-sm shadow-emerald-900/20 active:scale-95 transition-all cursor-pointer">
              <Plus className="w-4 h-4" />
              <span>Registrar Entrada</span>
            </button>
          </div>
        </motion.div>

        {/* ========================================================= */}
        {/* SECTION 1: TOP KPI CARDS WITH REACT-COUNTUP & DELAY       */}
        {/* ========================================================= */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {MOCK_KPIS.map((kpi) => {
            const Icon = kpi.icon;
            const isPositive = kpi.changeType === 'positive';

            return (
              <motion.div
                key={kpi.id}
                variants={itemVariants}
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 transition-all"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    {kpi.title}
                  </span>
                  <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] dark:text-emerald-400 flex items-center justify-center border border-[#047857]/10">
                    <Icon className="w-5 h-5 text-[#047857] dark:text-emerald-400" />
                  </div>
                </div>

                <div className="mt-4">
                  <div className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white font-mono">
                    <CountUp
                      start={0}
                      end={kpi.value}
                      duration={2.5}
                      separator=","
                      decimals={kpi.decimals ?? 0}
                      prefix={kpi.prefix}
                      suffix={kpi.suffix}
                      preserveValue
                    />
                  </div>
                </div>

                <div className="mt-3 flex items-center text-xs font-medium gap-1.5">
                  <span
                    className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[11px] font-semibold ${
                      isPositive
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                        : 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                    }`}
                  >
                    {isPositive ? (
                      <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                    ) : (
                      <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />
                    )}
                    {Math.abs(kpi.changePercentage)}%
                  </span>
                  <span className="text-gray-400 dark:text-gray-500">{kpi.comparisonText}</span>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* ========================================================= */}
        {/* SECTION 2: CHARTS & CATEGORY DISTRIBUTION                 */}
        {/* ========================================================= */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Trend AreaChart (2 columns on wide screens) */}
          <motion.div
            variants={itemVariants}
            className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 flex flex-col justify-between"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
              <div>
                <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <span>Fluctuación y Valuación del Inventario</span>
                  <span className="w-2 h-2 rounded-full bg-[#047857] animate-pulse"></span>
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Evolución acumulada del valor neto almacenado vs movimientos de almacén.
                </p>
              </div>

              {/* Timeframe Selector with Emerald Pill */}
              <div className="flex items-center bg-gray-100 dark:bg-gray-900/80 p-1 rounded-xl self-start sm:self-auto border border-gray-200/60 dark:border-gray-700/60">
                {(['7D', '30D', '90D', '1Y'] as const).map((period) => {
                  const isActive = selectedTimeframe === period;
                  return (
                    <button
                      key={period}
                      onClick={() => setSelectedTimeframe(period)}
                      className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                        isActive
                          ? 'bg-[#047857] text-white shadow-sm'
                          : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                      }`}
                    >
                      {period}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Recharts Area Chart Container */}
            <div className="w-full h-72 sm:h-80 -ml-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    {/* Linear gradient: 30% emerald (#047857) to 0% transparent */}
                    <linearGradient id="emeraldGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#047857" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#047857" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={isDarkMode ? '#374151' : '#f1f5f9'}
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: isDarkMode ? '#9ca3af' : '#64748b', fontSize: 11 }}
                    dy={8}
                  />

                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: isDarkMode ? '#9ca3af' : '#64748b', fontSize: 11 }}
                    tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
                    domain={['auto', 'auto']}
                    dx={-4}
                  />

                  <Tooltip
                    content={<CustomChartTooltip isDark={isDarkMode} />}
                    cursor={{
                      stroke: '#047857',
                      strokeWidth: 1.5,
                      strokeDasharray: '4 4',
                    }}
                  />

                  {/* Monotone curve in Emerald Accent #047857 with smooth drawing animation */}
                  <Area
                    type="monotone"
                    dataKey="inventoryValue"
                    name="Valor de Inventario"
                    stroke="#047857"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#emeraldGradient)"
                    isAnimationActive={true}
                    animationDuration={1500}
                    animationEasing="ease-out"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Chart Footer Indicator */}
            <div className="pt-4 mt-2 border-t border-gray-100 dark:border-gray-700/60 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#047857]"></span>
                  <span className="font-medium text-gray-700 dark:text-gray-300">
                    Valuación en Almacén
                  </span>
                </span>
                <span className="hidden sm:inline-block text-gray-400">•</span>
                <span className="hidden sm:inline-block">Cálculo activo: Costo Promedio Ponderado</span>
              </div>
              <span className="font-mono text-[11px] text-[#047857] dark:text-emerald-400 font-semibold">
                Auditado CFDI 4.0
              </span>
            </div>
          </motion.div>

          {/* Category Distribution Breakdown (1 column) */}
          <motion.div
            variants={itemVariants}
            className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-gray-900 dark:text-white">
                  Distribución por Categoría
                </h2>
                <span className="text-xs text-gray-400 font-mono">5 familias</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-5">
                Proporción del capital inmovilizado por línea de producto.
              </p>

              <div className="space-y-4">
                {MOCK_CATEGORIES.map((cat, idx) => (
                  <div key={cat.name} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-gray-700 dark:text-gray-200 truncate pr-2">
                        {cat.name}
                      </span>
                      <span className="font-mono text-gray-900 dark:text-white font-semibold">
                        ${cat.valuation.toLocaleString('es-MX')}
                      </span>
                    </div>

                    {/* Progress Bar with Emerald Tone Variation */}
                    <div className="w-full bg-gray-100 dark:bg-gray-700 h-2 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-1000 ease-out"
                        style={{
                          width: `${cat.percentage}%`,
                          backgroundColor:
                            idx === 0
                              ? '#047857'
                              : idx === 1
                              ? '#059669'
                              : idx === 2
                              ? '#10b981'
                              : idx === 3
                              ? '#34d399'
                              : '#6ee7b7',
                        }}
                      />
                    </div>
                    <div className="flex justify-between items-center text-[10px] text-gray-400">
                      <span>{cat.count} artículos en catálogo</span>
                      <span className="font-mono font-medium">{cat.percentage}% del total</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 mt-6 border-t border-gray-100 dark:border-gray-700/60">
              <button className="w-full py-2.5 px-3 rounded-xl border border-gray-200 dark:border-gray-700 text-xs font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-center gap-1.5 transition-all cursor-pointer">
                <span>Ver Resumen Contable Completo</span>
                <ChevronRight className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </motion.div>
        </div>

        {/* ========================================================= */}
        {/* SECTION 3: CRITICAL STOCK & REORDER TABLE LIST            */}
        {/* ========================================================= */}
        <motion.div
          variants={itemVariants}
          className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <span>Productos en Punto de Reorden y Nivel Crítico</span>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
                  Acción Requerida
                </span>
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Artículos cuya existencia física se encuentra por debajo del umbral de seguridad.
              </p>
            </div>

            {/* Filter and Search Bar */}
            <div className="flex items-center gap-2.5 flex-wrap">
              <div className="relative">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Buscar por SKU, nombre..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9 pr-3 py-1.5 text-xs rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#047857]/40 w-52 sm:w-64 transition-all"
                />
              </div>

              {/* Status Select Filter */}
              <div className="relative">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as any)}
                  className="px-3 py-1.5 text-xs rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-[#047857]/40 cursor-pointer"
                >
                  <option value="all">Todos los estados</option>
                  <option value="critical">Crítico (&lt; 50%)</option>
                  <option value="warning">Advertencia (&lt; 100%)</option>
                  <option value="optimal">Óptimo</option>
                </select>
              </div>
            </div>
          </div>

          {/* Table Container with smooth scrolling */}
          <div className="overflow-x-auto -mx-6 px-6">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700/60 text-gray-400 dark:text-gray-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-3">Artículo / SKU</th>
                  <th className="py-3 px-3">Categoría</th>
                  <th className="py-3 px-3 text-right">Existencia Actual</th>
                  <th className="py-3 px-3 text-right">Umbral Mínimo</th>
                  <th className="py-3 px-3 text-right">Costo Unitario</th>
                  <th className="py-3 px-3 text-center">Estado</th>
                  <th className="py-3 px-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
                {filteredProducts.length > 0 ? (
                  filteredProducts.map((prod) => (
                    <tr
                      key={prod.id}
                      className="hover:bg-gray-50/80 dark:hover:bg-gray-700/40 transition-colors"
                    >
                      <td className="py-3.5 px-3">
                        <div className="font-semibold text-gray-900 dark:text-white">
                          {prod.name}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="font-mono text-[11px] text-gray-500 dark:text-gray-400">
                            {prod.sku}
                          </span>
                          <span className="text-gray-300 dark:text-gray-600">•</span>
                          <span className="text-[11px] text-gray-400">{prod.location}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-3 text-gray-600 dark:text-gray-300">
                        {prod.category}
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono font-bold">
                        <span
                          className={
                            prod.status === 'critical'
                              ? 'text-rose-600 dark:text-rose-400'
                              : prod.status === 'warning'
                              ? 'text-amber-600 dark:text-amber-400'
                              : 'text-gray-900 dark:text-gray-100'
                          }
                        >
                          {prod.currentStock} uds
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono text-gray-500 dark:text-gray-400">
                        {prod.minThreshold} uds
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono text-gray-900 dark:text-gray-200">
                        ${prod.unitCost.toFixed(2)}
                      </td>
                      <td className="py-3.5 px-3 text-center">
                        {prod.status === 'critical' ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 dark:bg-rose-950/70 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
                            Crítico
                          </span>
                        ) : prod.status === 'warning' ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900">
                            Por Reordenar
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                            Óptimo
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <button className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#047857] hover:bg-emerald-800 text-white transition-all shadow-sm active:scale-95 cursor-pointer">
                          Reabastecer
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-gray-400 text-xs">
                      No se encontraron artículos con los criterios seleccionados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* ========================================================= */}
        {/* FOOTER AUDIT BAR                                          */}
        {/* ========================================================= */}
        <motion.div
          variants={itemVariants}
          className="flex flex-col sm:flex-row items-center justify-between text-xs text-gray-400 dark:text-gray-500 pt-2 border-t border-gray-200/60 dark:border-gray-800"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#047857]" />
            <span>Kardex Sincronizado | Consistencia Referencial en Memoria</span>
          </div>
          <div className="flex items-center gap-3 mt-2 sm:mt-0">
            <span>Motor PEPS & Promedio Ponderado</span>
            <span>•</span>
            <span className="text-[#047857] dark:text-emerald-400 font-semibold">
              Anexo 24 SAT Compliant
            </span>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default InventoryDashboard;
