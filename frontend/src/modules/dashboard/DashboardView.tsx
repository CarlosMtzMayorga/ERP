import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { motion, Variants } from 'framer-motion';
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
  ArrowUpRight,
  ArrowDownRight,
  FileCheck2,
  Building2,
  Clock,
  ShieldCheck,
  CheckCircle2,
  Activity,
  Layers,
  ChevronRight,
  Boxes,
  ShoppingCart,
  Receipt,
  CreditCard,
  Truck,
  Wallet,
  Landmark,
  Users,
  BookOpen,
  Settings,
} from 'lucide-react';
import { Link } from 'react-router-dom';

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

const REVENUE_TREND_DATA = [
  { month: 'Mayo', sales: 185000, expenses: 130000, profit: 55000 },
  { month: 'Junio', sales: 210000, expenses: 142000, profit: 68000 },
  { month: 'Julio', sales: 198000, expenses: 138000, profit: 60000 },
  { month: 'Agosto', sales: 235000, expenses: 155000, profit: 80000 },
  { month: 'Septiembre', sales: 254000, expenses: 162000, profit: 92000 },
  { month: 'Octubre', sales: 284500, expenses: 171000, profit: 113500 },
];

export const DashboardView: React.FC = () => {
  const { activeTenant, user } = useAuth();
  const { isDark } = useTheme();

  const ERP_MODULES = [
    { id: 1, name: 'Configurador', path: '/config', icon: Settings, desc: 'Empresas, Folios, Certificados CSD en Memoria' },
    { id: 2, name: 'Inventarios', path: '/inventory', icon: Boxes, desc: 'Multialmacén, Kardex Inmutable, PEPS y Promedio' },
    { id: 3, name: 'Ventas', path: '/sales', icon: ShoppingCart, desc: 'Cotizaciones, Pedidos, Remisiones, Facturas CFDI 4.0' },
    { id: 4, name: 'Punto de Venta (POS)', path: '/pos', icon: Receipt, desc: 'Turnos, Cortes X/Z, Facturación Global SAT' },
    { id: 5, name: 'Cuentas por Cobrar', path: '/cxc', icon: CreditCard, desc: 'Límites de crédito, Saldos vencidos, REP 2.0' },
    { id: 6, name: 'Compras', path: '/purchases', icon: Truck, desc: 'Requisiciones, OC, Backorders, Valuación PEPS' },
    { id: 7, name: 'Cuentas por Pagar', path: '/cxp', icon: Wallet, desc: 'Pasivos reales, Vencimientos, Retenciones ISR/IVA' },
    { id: 8, name: 'Bancos', path: '/banking', icon: Landmark, desc: 'Chequeras, Dispersión, Bloqueo Anti-Sobregiro' },
    { id: 9, name: 'Nómina', path: '/payroll', icon: Users, desc: 'Cálculo LISR, IMSS Obrero-Patronal, CFDI 1.2' },
    { id: 10, name: 'Contabilidad', path: '/accounting', icon: BookOpen, desc: 'Partida doble, Balanza SAT Anexo 24, P&L' },
  ];

  return (
    <motion.div
      className="space-y-6 max-w-7xl mx-auto"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Welcome Banner */}
      <motion.div
        variants={itemVariants}
        className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-gray-800 p-6 rounded-2xl border border-gray-100 dark:border-gray-700/60 shadow-sm transition-all"
      >
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] flex items-center justify-center border border-[#047857]/20">
              <ShieldCheck className="w-5 h-5 text-[#047857]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">
                Panel General | {activeTenant ? activeTenant.legal_name : 'ERP SaaS'}
              </h1>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 flex items-center gap-2">
                <span>Bienvenido, <strong className="text-gray-700 dark:text-gray-200">{user?.full_name}</strong></span>
                <span>•</span>
                <span className="font-mono bg-emerald-50 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300 px-2 py-0.5 rounded text-[11px] font-semibold border border-emerald-200 dark:border-emerald-800">
                  RFC: {activeTenant?.rfc || 'N/A'}
                </span>
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-emerald-50 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <span className="w-2 h-2 rounded-full bg-[#047857] animate-pulse"></span>
            SAT CFDI 4.0 / Anexo 20 Activo
          </div>
        </div>
      </motion.div>

      {/* KPI Cards with React-CountUp */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* KPI 1 */}
        <motion.div
          variants={itemVariants}
          whileHover={{ y: -3, transition: { duration: 0.2 } }}
          className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 transition-all"
        >
          <div className="flex items-center justify-between text-gray-500 dark:text-gray-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Ventas del Mes</span>
            <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] dark:text-emerald-400 flex items-center justify-center border border-[#047857]/10">
              <TrendingUp className="w-5 h-5 text-[#047857] dark:text-emerald-400" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white font-mono">
              <CountUp start={0} end={284500} duration={2.5} separator="," decimals={2} prefix="$" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium gap-1.5">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
              <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
              12.4%
            </span>
            <span className="text-gray-400 dark:text-gray-500">vs. mes anterior</span>
          </div>
        </motion.div>

        {/* KPI 2 */}
        <motion.div
          variants={itemVariants}
          whileHover={{ y: -3, transition: { duration: 0.2 } }}
          className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 transition-all"
        >
          <div className="flex items-center justify-between text-gray-500 dark:text-gray-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Cuentas por Cobrar</span>
            <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] dark:text-emerald-400 flex items-center justify-center border border-[#047857]/10">
              <Clock className="w-5 h-5 text-[#047857] dark:text-emerald-400" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white font-mono">
              <CountUp start={0} end={84120} duration={2.5} separator="," decimals={2} prefix="$" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium gap-1.5">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
              3 facturas por vencer
            </span>
          </div>
        </motion.div>

        {/* KPI 3 */}
        <motion.div
          variants={itemVariants}
          whileHover={{ y: -3, transition: { duration: 0.2 } }}
          className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 transition-all"
        >
          <div className="flex items-center justify-between text-gray-500 dark:text-gray-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Valor de Inventario</span>
            <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] dark:text-emerald-400 flex items-center justify-center border border-[#047857]/10">
              <Package className="w-5 h-5 text-[#047857] dark:text-emerald-400" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white font-mono">
              <CountUp start={0} end={894320} duration={2.5} separator="," decimals={2} prefix="$" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium text-gray-400 dark:text-gray-500">
            <span>PEPS & Promedio Activo</span>
          </div>
        </motion.div>

        {/* KPI 4 */}
        <motion.div
          variants={itemVariants}
          whileHover={{ y: -3, transition: { duration: 0.2 } }}
          className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60 transition-all"
        >
          <div className="flex items-center justify-between text-gray-500 dark:text-gray-400">
            <span className="text-xs font-semibold uppercase tracking-wider">CFDIs Timbrados</span>
            <div className="w-10 h-10 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] dark:text-emerald-400 flex items-center justify-center border border-[#047857]/10">
              <FileCheck2 className="w-5 h-5 text-[#047857] dark:text-emerald-400" />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white font-mono">
              <CountUp start={0} end={3842} duration={2.5} separator="," suffix=" folios" />
            </div>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium text-[#047857] dark:text-emerald-400">
            <span>Bloqueo Atómico Activo</span>
          </div>
        </motion.div>
      </div>

      {/* Main Revenue Trend Chart (Recharts AreaChart) */}
      <motion.div
        variants={itemVariants}
        className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700/60"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <span>Tendencia Consolidada de Ingresos vs Egresos</span>
              <span className="w-2 h-2 rounded-full bg-[#047857] animate-pulse"></span>
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Cierre contable acumulado y flujo operativo en tiempo real.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#047857]"></span>
              <span className="text-gray-600 dark:text-gray-300 font-medium">Facturación</span>
            </span>
          </div>
        </div>

        <div className="w-full h-72 -ml-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={REVENUE_TREND_DATA} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="generalRevenueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#047857" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#047857" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#374151' : '#f1f5f9'} vertical={false} />
              <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: isDark ? '#9ca3af' : '#64748b', fontSize: 11 }} dy={8} />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: isDark ? '#9ca3af' : '#64748b', fontSize: 11 }}
                tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
                domain={['auto', 'auto']}
                dx={-4}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className={`p-4 rounded-xl shadow-xl border text-xs font-sans backdrop-blur-md ${isDark ? 'bg-gray-800/95 border-gray-700 text-gray-100' : 'bg-white/95 border-gray-200 text-gray-800'}`}>
                        <p className="font-semibold text-sm mb-1 text-[#047857]">{label}</p>
                        <p className="text-gray-500">Ventas: <strong className="text-gray-900 dark:text-white">${data.sales.toLocaleString('es-MX')}</strong></p>
                        <p className="text-gray-500">Egresos: <strong className="text-rose-500">-${data.expenses.toLocaleString('es-MX')}</strong></p>
                        <p className="text-gray-500 pt-1 border-t border-gray-100 dark:border-gray-700 mt-1">Margen Neto: <strong className="text-emerald-600 dark:text-emerald-400">+${data.profit.toLocaleString('es-MX')}</strong></p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area
                type="monotone"
                dataKey="sales"
                name="Ventas"
                stroke="#047857"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#generalRevenueGradient)"
                isAnimationActive={true}
                animationDuration={1500}
                animationEasing="ease-out"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Module Overview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          variants={itemVariants}
          className="lg:col-span-2 bg-white dark:bg-gray-800 p-6 rounded-2xl border border-gray-100 dark:border-gray-700/60 shadow-sm"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-gray-900 dark:text-white">
              Ecosistema Modular del ERP
            </h2>
            <span className="text-xs text-gray-400 font-mono">10 Módulos Operativos</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {ERP_MODULES.map((m) => {
              const Icon = m.icon;
              return (
                <Link
                  key={m.id}
                  to={m.path}
                  className="p-3.5 rounded-xl border border-gray-100 dark:border-gray-700/60 bg-gray-50/60 dark:bg-gray-900/40 hover:bg-[#047857]/5 dark:hover:bg-[#047857]/10 hover:border-[#047857]/40 transition-all group flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] flex items-center justify-center">
                        <Icon className="w-4 h-4 text-[#047857]" />
                      </div>
                      <span className="text-xs font-bold text-gray-900 dark:text-white group-hover:text-[#047857] dark:group-hover:text-emerald-400 transition-colors">
                        {m.id}. {m.name}
                      </span>
                    </div>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      Activo
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-2 line-clamp-1">
                    {m.desc}
                  </p>
                </Link>
              );
            })}
          </div>
        </motion.div>

        {/* Right Info Box */}
        <motion.div
          variants={itemVariants}
          className="bg-white dark:bg-gray-800 p-6 rounded-2xl border border-gray-100 dark:border-gray-700/60 shadow-sm flex flex-col justify-between"
        >
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-[#047857]" />
              <span>Aislamiento Multi-Tenant</span>
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
              Cada transacción está garantizada a nivel base de datos mediante clave de tenant forzosa y
              Row-Level Security (RLS) en PostgreSQL, garantizando aislamiento estricto y alta concurrencia
              sin riesgo de fuga de datos entre empresas.
            </p>
            <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200/80 dark:border-gray-700 text-xs font-mono text-gray-600 dark:text-gray-300 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-400">Tenant Activo:</span>
                <span className="text-[#047857] dark:text-emerald-400 font-semibold">{activeTenant?.id.slice(0, 8)}...</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Régimen Fiscal:</span>
                <span>601 General de Ley</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Versión CFDI:</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">4.0 / Anexo 20</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Motor DB:</span>
                <span>PostgreSQL 16 Enterprise</span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-100 dark:border-gray-700/60 text-center">
            <span className="text-xs text-gray-400 block font-mono">
              Sistema ERP 100% Sincronizado
            </span>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default DashboardView;
