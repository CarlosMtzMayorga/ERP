import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  FileText,
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ArrowUpRight,
  ArrowDownRight,
  Layers,
  User,
  Building2,
  Calendar,
} from 'lucide-react';

interface LayerConsumption {
  cost_layer_id: string;
  quantity_consumed: number;
  unit_cost: number;
  total_cost: number;
}

interface KardexItem {
  id: string;
  created_at: string;
  product_id: string;
  sku: string;
  product_name: string;
  warehouse_id: string;
  warehouse_name: string;
  movement_type: string;
  direction: 'IN' | 'OUT';
  quantity: number;
  unit_cost: number;
  total_cost: number;
  previous_stock: number;
  new_stock: number;
  new_avg_cost: number;
  costing_method: string;
  reference_type: string;
  reference_folio?: string;
  notes?: string;
  user_name?: string;
  layer_consumptions: LayerConsumption[];
}

export const KardexTab: React.FC = () => {
  const [movements, setMovements] = useState<KardexItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [search, setSearch] = useState('');

  const fetchKardex = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<KardexItem[]>('/inventory/kardex', {
        params: { limit: 100 },
      });
      setMovements(res.data);
    } catch (err) {
      console.error('Error fetching kardex:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKardex();
  }, []);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const filteredMovements = movements.filter((m) => {
    const matchesSearch =
      m.product_name.toLowerCase().includes(search.toLowerCase()) ||
      m.sku.toLowerCase().includes(search.toLowerCase()) ||
      (m.reference_folio && m.reference_folio.toLowerCase().includes(search.toLowerCase()));
    const matchesType = !typeFilter || m.movement_type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-soft flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar por artículo, SKU o folio..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-blue-500/20 text-slate-700"
          >
            <option value="">Todos los Tipos de Movimiento</option>
            <option value="ENTRADA_COMPRA">Entrada por Compra</option>
            <option value="SALIDA_VENTA">Salida por Venta / Factura</option>
            <option value="TRASPASO_ENTRADA">Traspaso Entrada</option>
            <option value="TRASPASO_SALIDA">Traspaso Salida</option>
            <option value="AJUSTE_POSITIVO">Ajuste Positivo</option>
            <option value="AJUSTE_NEGATIVO">Ajuste Negativo</option>
          </select>

          <button
            onClick={fetchKardex}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
            title="Refrescar Kardex"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Kardex Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-5 py-4">Fecha & Hora</th>
                <th className="px-5 py-4">Tipo Movimiento</th>
                <th className="px-5 py-4">Folio Ref.</th>
                <th className="px-5 py-4">Artículo</th>
                <th className="px-5 py-4">Almacén</th>
                <th className="px-5 py-4 text-right">Cantidad</th>
                <th className="px-5 py-4 text-right">Costo Unit.</th>
                <th className="px-5 py-4 text-right">Costo Total</th>
                <th className="px-5 py-4 text-right">Stock Final</th>
                <th className="px-5 py-4 text-center">Auditoría</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={10} className="text-center py-10 text-slate-400">
                    Consultando ledger inmutable de movimientos...
                  </td>
                </tr>
              ) : filteredMovements.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center py-10 text-slate-400">
                    No se han registrado movimientos de inventario todavía.
                  </td>
                </tr>
              ) : (
                filteredMovements.map((m) => {
                  const isExpanded = expandedId === m.id;
                  const isEntry = m.direction === 'IN';
                  return (
                    <React.Fragment key={m.id}>
                      <tr
                        onClick={() => toggleExpand(m.id)}
                        className={`hover:bg-slate-50 cursor-pointer transition-colors ${
                          isExpanded ? 'bg-blue-50/30' : ''
                        }`}
                      >
                        <td className="px-5 py-3.5 text-slate-500 font-mono">
                          {new Date(m.created_at).toLocaleString('es-MX', {
                            dateStyle: 'short',
                            timeStyle: 'short',
                          })}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                              isEntry
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {isEntry ? (
                              <ArrowDownRight className="w-3 h-3 text-emerald-600" />
                            ) : (
                              <ArrowUpRight className="w-3 h-3 text-rose-600" />
                            )}
                            <span>{m.movement_type}</span>
                          </span>
                        </td>
                        <td className="px-5 py-3.5 font-mono font-semibold text-slate-800">
                          {m.reference_folio || 'S/F'}
                        </td>
                        <td className="px-5 py-3.5">
                          <div className="font-bold text-slate-900">{m.product_name}</div>
                          <div className="text-[10px] text-slate-400 font-mono">SKU: {m.sku}</div>
                        </td>
                        <td className="px-5 py-3.5 text-slate-700">{m.warehouse_name}</td>
                        <td
                          className={`px-5 py-3.5 text-right font-mono font-bold text-sm ${
                            isEntry ? 'text-emerald-600' : 'text-slate-800'
                          }`}
                        >
                          {isEntry ? '+' : '-'}
                          {Number(m.quantity).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-5 py-3.5 text-right font-mono text-slate-600">
                          ${Number(m.unit_cost).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-5 py-3.5 text-right font-mono font-bold text-slate-900">
                          ${Number(m.total_cost).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-5 py-3.5 text-right font-mono text-slate-700 font-semibold">
                          {Number(m.new_stock).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-5 py-3.5 text-center">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExpand(m.id);
                            }}
                            className="p-1 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-700 transition-colors"
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Audit Drawer */}
                      {isExpanded && (
                        <tr className="bg-slate-50/80">
                          <td colSpan={10} className="px-8 py-4 border-y border-slate-200">
                            <div className="space-y-3">
                              <div className="flex flex-wrap items-center justify-between text-xs text-slate-600 gap-4">
                                <div className="flex items-center gap-2">
                                  <User className="w-4 h-4 text-blue-600" />
                                  <span>
                                    Usuario Autorizador:{' '}
                                    <strong className="text-slate-900">{m.user_name || 'Sistema'}</strong>
                                  </span>
                                </div>
                                <div>
                                  <span>Método de Costeo: </span>
                                  <span className="font-bold text-slate-900">{m.costing_method}</span>
                                </div>
                                <div>
                                  <span>Stock previo al movimiento: </span>
                                  <span className="font-mono font-bold text-slate-800">
                                    {Number(m.previous_stock).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                                  </span>
                                </div>
                                {m.notes && (
                                  <div className="w-full text-slate-500 italic bg-white p-2.5 rounded-xl border border-slate-200">
                                    Notas: {m.notes}
                                  </div>
                                )}
                              </div>

                              {/* Detailed PEPS Cost Layers Consumed (if any) */}
                              {m.layer_consumptions && m.layer_consumptions.length > 0 && (
                                <div className="mt-3 bg-white p-3 rounded-xl border border-purple-200">
                                  <div className="flex items-center gap-1.5 text-xs font-bold text-purple-900 mb-2">
                                    <Layers className="w-4 h-4 text-purple-600" />
                                    <span>Capas de Costo PEPS (FIFO) Afectadas:</span>
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    {m.layer_consumptions.map((c, idx) => (
                                      <div
                                        key={idx}
                                        className="p-2 bg-purple-50/60 rounded-lg border border-purple-100 text-[11px] font-mono text-purple-950"
                                      >
                                        <div>
                                          Consumido:{' '}
                                          <strong>{Number(c.quantity_consumed).toFixed(2)} uds</strong>
                                        </div>
                                        <div>Costo Capa: ${Number(c.unit_cost).toFixed(2)}</div>
                                        <div>Subtotal: ${Number(c.total_cost).toFixed(2)}</div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

