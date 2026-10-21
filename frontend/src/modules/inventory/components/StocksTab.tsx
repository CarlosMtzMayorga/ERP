import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  Boxes,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  PackageCheck,
  Building2,
  DollarSign,
  Search,
  Filter,
  RefreshCw,
  PlusCircle,
  ArrowRightLeft,
} from 'lucide-react';

export interface ProductStockItem {
  product_id: string;
  sku: string;
  product_name: string;
  unit_name: string;
  costing_method: string;
  warehouse_id: string;
  warehouse_name: string;
  physical_stock: number;
  reserved_stock: number;
  available_stock: number;
  average_cost: number;
  last_cost: number;
  total_value: number;
  min_stock: number;
  reorder_point: number;
  max_stock: number;
  stock_status: 'CRITICAL' | 'REORDER' | 'OPTIMAL';
}

interface StocksTabProps {
  onOpenMovementModal: (type: 'entry' | 'exit' | 'transfer', product?: ProductStockItem) => void;
}

export const StocksTab: React.FC<StocksTabProps> = ({ onOpenMovementModal }) => {
  const [stocks, setStocks] = useState<ProductStockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const fetchStocks = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<ProductStockItem[]>('/inventory/stocks');
      setStocks(res.data);
    } catch (err) {
      console.error('Error fetching stocks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStocks();
  }, []);

  const getStatusBadge = (status: ProductStockItem['stock_status']) => {
    if (status === 'CRITICAL') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
          <XCircle className="w-3 h-3 text-rose-600 animate-pulse" />
          <span>Crítico (≤ Mínimo)</span>
        </span>
      );
    }
    if (status === 'REORDER') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3 h-3 text-amber-600" />
          <span>Reabastecer</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        <span>Óptimo</span>
      </span>
    );
  };

  const filteredStocks = stocks.filter((s) => {
    const matchesSearch =
      s.product_name.toLowerCase().includes(search.toLowerCase()) ||
      s.sku.toLowerCase().includes(search.toLowerCase()) ||
      s.warehouse_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || s.stock_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-4">
      {/* Search and Filters Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-soft flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar por SKU, artículo o almacén..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-semibold text-slate-600">
            <button
              onClick={() => setStatusFilter('ALL')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                statusFilter === 'ALL' ? 'bg-white text-slate-900 shadow-sm' : 'hover:text-slate-900'
              }`}
            >
              Todos ({stocks.length})
            </button>
            <button
              onClick={() => setStatusFilter('CRITICAL')}
              className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
                statusFilter === 'CRITICAL' ? 'bg-white text-rose-700 shadow-sm' : 'hover:text-slate-900'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Críticos
            </button>
            <button
              onClick={() => setStatusFilter('REORDER')}
              className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
                statusFilter === 'REORDER' ? 'bg-white text-amber-700 shadow-sm' : 'hover:text-slate-900'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              Reorden
            </button>
          </div>

          <button
            onClick={fetchStocks}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors ml-auto sm:ml-0"
            title="Refrescar existencias"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stocks Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-5 py-4">Artículo & SKU</th>
                <th className="px-5 py-4">Almacén</th>
                <th className="px-5 py-4 text-center">Costeo</th>
                <th className="px-5 py-4 text-right">Exist. Física</th>
                <th className="px-5 py-4 text-right">Apartados</th>
                <th className="px-5 py-4 text-right font-bold text-slate-800">Disponible</th>
                <th className="px-5 py-4 text-right">Costo Unit.</th>
                <th className="px-5 py-4 text-right">Valor Total</th>
                <th className="px-5 py-4 text-center">Semáforo</th>
                <th className="px-5 py-4 text-right">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={10} className="text-center py-10 text-slate-400">
                    Calculando existencias y capas de costo...
                  </td>
                </tr>
              ) : filteredStocks.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center py-10 text-slate-400">
                    No hay existencias registradas con los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                filteredStocks.map((item) => (
                  <tr key={`${item.warehouse_id}-${item.product_id}`} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="font-bold text-slate-900">{item.product_name}</div>
                      <div className="text-[11px] font-mono text-blue-600">SKU: {item.sku}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1.5 text-slate-700">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        <span>{item.warehouse_name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.costing_method === 'PEPS'
                          ? 'bg-purple-50 text-purple-700 border border-purple-200'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}>
                        {item.costing_method}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-semibold text-slate-800">
                      {Number(item.physical_stock).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-amber-600">
                      {Number(item.reserved_stock) > 0 ? (
                        <span className="px-1.5 py-0.5 rounded bg-amber-50 font-semibold">
                          {Number(item.reserved_stock).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-blue-600 text-sm">
                      {Number(item.available_stock).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-slate-600">
                      ${Number(item.average_cost).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-slate-900">
                      ${Number(item.total_value).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      {getStatusBadge(item.stock_status)}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => onOpenMovementModal('entry', item)}
                          className="px-2 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-lg text-[11px] font-semibold transition-colors"
                          title="Entrada / Ajuste +"
                        >
                          + Entrada
                        </button>
                        <button
                          onClick={() => onOpenMovementModal('exit', item)}
                          className="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg text-[11px] font-semibold transition-colors"
                          title="Salida / Ajuste -"
                        >
                          - Salida
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
