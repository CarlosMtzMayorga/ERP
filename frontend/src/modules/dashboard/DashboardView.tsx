import React from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  TrendingUp,
  Receipt,
  AlertCircle,
  Package,
  ArrowUpRight,
  ArrowDownRight,
  FileCheck2,
  Building2,
  Clock,
} from 'lucide-react';

export const DashboardView: React.FC = () => {
  const { activeTenant, user } = useAuth();

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-soft">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Panel General | {activeTenant ? activeTenant.legal_name : 'ERP SaaS'}
          </h1>
          <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
            <span>Bienvenido, <strong className="text-slate-700">{user?.full_name}</strong></span>
            <span>•</span>
            <span className="font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-xs">
              RFC: {activeTenant?.rfc || 'N/A'}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            SAT CFDI 4.0 Conectado
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Ventas del Mes</span>
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">$248,500.00</span>
            <span className="text-xs text-slate-400 font-normal ml-1">MXN</span>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium text-emerald-600">
            <ArrowUpRight className="w-4 h-4 mr-0.5" />
            <span>+12.4% vs mes anterior</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Cuentas por Cobrar</span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">$84,120.00</span>
            <span className="text-xs text-slate-400 font-normal ml-1">MXN</span>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium text-amber-600">
            <span>3 facturas por vencer hoy</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Valor de Inventario</span>
            <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Package className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">$512,940.00</span>
            <span className="text-xs text-slate-400 font-normal ml-1">MXN</span>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium text-slate-500">
            <span>Costeo Promedio Activo</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">CFDIs Timbrados</span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <FileCheck2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">142</span>
            <span className="text-xs text-slate-400 font-normal ml-1">Folios</span>
          </div>
          <div className="mt-3 flex items-center text-xs font-medium text-emerald-600">
            <span>PAC Finkok 100% Operativo</span>
          </div>
        </div>
      </div>

      {/* Module Overview & Status Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-slate-900">Estado de Módulos ERP</h2>
            <span className="text-xs text-slate-500 font-medium">Arquitectura Modular Inspirada en Microsip</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { id: 1, name: 'Configurador', status: 'Activo', desc: 'Empresas, Folios, Certificados CSD' },
              { id: 2, name: 'Inventarios', status: 'Activo', desc: 'Multialmacén, Costeo PEPS/Promedio' },
              { id: 3, name: 'Ventas', status: 'Activo', desc: 'Cotizaciones, Pedidos, Remisiones, Facturas' },
              { id: 4, name: 'Punto de Venta (POS)', status: 'Activo', desc: 'Caja rápida, Cortes X/Z, Factura Global' },
              { id: 5, name: 'Cuentas por Cobrar', status: 'Activo', desc: 'Créditos, Antigüedad de Saldos, REP 2.0' },
              { id: 6, name: 'Compras', status: 'Activo', desc: 'Requisiciones, OC, Recepción, XML SAT' },
              { id: 7, name: 'Cuentas por Pagar', status: 'Activo', desc: 'Vencimientos, Pagos a Proveedores' },
              { id: 8, name: 'Bancos', status: 'Activo', desc: 'Cuentas de Cheques, Conciliación Bancaria' },
              { id: 9, name: 'Nómina', status: 'Activo', desc: 'Cálculo IMSS/ISR, Recibos CFDI 1.2' },
              { id: 10, name: 'Contabilidad', status: 'Activo', desc: 'Pólizas automáticas, Balanza SAT' },
            ].map((m) => (
              <div key={m.id} className="p-3.5 rounded-xl border border-slate-100 hover:border-blue-200 bg-slate-50/50 hover:bg-blue-50/20 transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800">{m.id}. {m.name}</span>
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                    {m.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">{m.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right Info Box */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-soft flex flex-col justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 mb-2">Aislamiento Multiempresa</h2>
            <p className="text-xs text-slate-500 leading-relaxed">
              Cada transacción está garantizada a nivel base de datos mediante <code>tenant_id</code> y
              Row-Level Security (RLS) en PostgreSQL, garantizando aislamiento estricto y alta concurrencia
              sin riesgo de fuga de datos entre empresas.
            </p>
            <div className="mt-4 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs font-mono text-slate-600 space-y-1">
              <div>Tenant ID: <span className="text-blue-600">{activeTenant?.id.slice(0, 8)}...</span></div>
              <div>Regimen Fiscal: <span>601 General de Ley</span></div>
              <div>Versión CFDI: <span>4.0 Anexo 20</span></div>
              <div>Motor DB: <span>AWS RDS PostgreSQL</span></div>
            </div>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-100">
            <span className="text-xs text-slate-400 block text-center">
              Fase 1 completada • Esperando confirmación para Fase 2
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
