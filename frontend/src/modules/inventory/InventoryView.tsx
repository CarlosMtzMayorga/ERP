import React, { useState, useEffect } from 'react';
import { apiClient } from '../../api/axiosClient';
import {
  Boxes,
  Layers,
  TrendingUp,
  AlertTriangle,
  Package,
  Plus,
  RefreshCw,
  Clock,
  ArrowRightLeft,
} from 'lucide-react';
import { StocksTab, ProductStockItem } from './components/StocksTab';
import { KardexTab } from './components/KardexTab';
import { MovementModal } from './components/MovementModal';

interface DashboardMetrics {
  total_valuation: number;
  total_physical_units: number;
  critical_stock_count: number;
  reorder_stock_count: number;
  movements_today_count: number;
  active_reservations_count: number;
}

export const InventoryView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'stocks' | 'kardex'>('stocks');
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalType, setModalType] = useState<'entry' | 'exit' | 'transfer'>('entry');
  const [selectedProduct, setSelectedProduct] = useState<ProductStockItem | undefined>(undefined);

  const fetchMetrics = async () => {
    try {
      const res = await apiClient.get<DashboardMetrics>('/inventory/dashboard');
      setMetrics(res.data);
    } catch (err) {
      console.error('Error fetching inventory metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const openMovementModal = (type: 'entry' | 'exit' | 'transfer', product?: ProductStockItem) => {
    setModalType(type);
    setSelectedProduct(product);
    setIsModalOpen(true);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Title & Quick Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Boxes className="w-6 h-6 text-blue-600" />
            <span>Módulo 2: Inventarios Multialmacén</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Kardex inmutable (Append-Only), motor de costeo dual (PEPS / Promedio) y soft allocation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => openMovementModal('entry')}
            className="flex items-center gap-2 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-emerald-500/20 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Entrada / Ajuste +</span>
          </button>
          <button
            onClick={() => openMovementModal('exit')}
            className="flex items-center gap-2 px-3.5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-rose-500/20 transition-all cursor-pointer"
          >
            <span>Salida / Merma -</span>
          </button>
          <button
            onClick={() => openMovementModal('transfer')}
            className="flex items-center gap-2 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 transition-all cursor-pointer"
          >
            <ArrowRightLeft className="w-4 h-4" />
            <span>Traspaso</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Valor de Inventario</span>
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">
              ${metrics ? Number(metrics.total_valuation).toLocaleString('es-MX', { minimumFractionDigits: 2 }) : '0.00'}
            </span>
            <span className="text-xs text-slate-400 ml-1">MXN</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">
            Costo Promedio Ponderado + Capas PEPS
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Existencia Física Total</span>
            <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Package className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">
              {metrics ? Number(metrics.total_physical_units).toLocaleString('es-MX', { minimumFractionDigits: 0 }) : '0'}
            </span>
            <span className="text-xs text-slate-400 ml-1">Unidades</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">
            Conteo físico en todos los almacenes
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Semáforo Crítico</span>
            <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-rose-600">
              {metrics ? metrics.critical_stock_count : '0'}
            </span>
            <span className="text-xs text-slate-400 ml-1">SKUs</span>
          </div>
          <div className="mt-2 text-[11px] text-rose-600 font-medium">
            Existencia ≤ Stock Mínimo
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Movimientos de Hoy</span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">
              {metrics ? metrics.movements_today_count : '0'}
            </span>
            <span className="text-xs text-slate-400 ml-1">Kardex</span>
          </div>
          <div className="mt-2 text-[11px] text-emerald-600 font-medium">
            Ledger Append-Only al día
          </div>
        </div>
      </div>

      {/* Tabs Switcher Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('stocks')}
          className={`flex items-center gap-2 pb-3 px-2 text-xs font-semibold transition-all border-b-2 cursor-pointer ${
            activeTab === 'stocks'
              ? 'border-blue-600 text-blue-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Boxes className="w-4 h-4" />
          <span>Existencias & Semáforos de Stock</span>
        </button>
        <button
          onClick={() => setActiveTab('kardex')}
          className={`flex items-center gap-2 pb-3 px-2 text-xs font-semibold transition-all border-b-2 cursor-pointer ${
            activeTab === 'kardex'
              ? 'border-blue-600 text-blue-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Historial Kardex Inmutable & Capas PEPS</span>
        </button>
      </div>

      {/* Active Tab View */}
      {activeTab === 'stocks' ? (
        <StocksTab onOpenMovementModal={openMovementModal} />
      ) : (
        <KardexTab />
      )}

      {/* Modal for Movements */}
      <MovementModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          fetchMetrics();
        }}
        initialType={modalType}
        preselectedProduct={selectedProduct}
      />
    </div>
  );
};

