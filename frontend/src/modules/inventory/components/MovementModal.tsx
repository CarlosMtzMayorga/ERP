import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import { ProductStockItem } from './StocksTab';
import {
  Boxes,
  ArrowDownRight,
  ArrowUpRight,
  ArrowRightLeft,
  DollarSign,
  Building2,
  FileText,
} from 'lucide-react';

interface MovementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialType: 'entry' | 'exit' | 'transfer';
  preselectedProduct?: ProductStockItem;
}

interface WarehouseOption {
  id: string;
  code: string;
  name: string;
}

export const MovementModal: React.FC<MovementModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialType,
  preselectedProduct,
}) => {
  const [movementMode, setMovementMode] = useState<'entry' | 'exit' | 'transfer'>(initialType);
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [products, setProducts] = useState<ProductStockItem[]>([]);
  const [selectedProductId, setSelectedProductId] = useState(preselectedProduct?.product_id || '');
  const [sourceWarehouseId, setSourceWarehouseId] = useState(preselectedProduct?.warehouse_id || '');
  const [targetWarehouseId, setTargetWarehouseId] = useState('');
  const [quantity, setQuantity] = useState<string>('1');
  const [unitCost, setUnitCost] = useState<string>(preselectedProduct?.average_cost?.toString() || '0');
  const [folio, setFolio] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMovementMode(initialType);
    if (preselectedProduct) {
      setSelectedProductId(preselectedProduct.product_id);
      setSourceWarehouseId(preselectedProduct.warehouse_id);
      setUnitCost(preselectedProduct.average_cost?.toString() || '0');
    }
  }, [initialType, preselectedProduct]);

  useEffect(() => {
    const fetchSelectData = async () => {
      try {
        const [wRes, pRes] = await Promise.all([
          apiClient.get<WarehouseOption[]>('/tenants/branches'), // Or warehouses
          apiClient.get<ProductStockItem[]>('/inventory/stocks'),
        ]);
        setProducts(pRes.data);
        if (pRes.data.length > 0 && !selectedProductId) {
          setSelectedProductId(pRes.data[0].product_id);
          setSourceWarehouseId(pRes.data[0].warehouse_id);
        }
      } catch (err) {
        console.error('Error fetching select data:', err);
      }
    };
    if (isOpen) {
      fetchSelectData();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (movementMode === 'entry') {
        await apiClient.post('/inventory/movements/entry', {
          warehouse_id: sourceWarehouseId,
          product_id: selectedProductId,
          quantity: parseFloat(quantity),
          unit_cost: parseFloat(unitCost),
          movement_type: 'AJUSTE_POSITIVO',
          reference_folio: folio || null,
          notes: notes || null,
        });
      } else if (movementMode === 'exit') {
        await apiClient.post('/inventory/movements/exit', {
          warehouse_id: sourceWarehouseId,
          product_id: selectedProductId,
          quantity: parseFloat(quantity),
          movement_type: 'AJUSTE_NEGATIVO',
          reference_folio: folio || null,
          notes: notes || null,
        });
      } else {
        await apiClient.post('/inventory/movements/transfer', {
          source_warehouse_id: sourceWarehouseId,
          target_warehouse_id: targetWarehouseId,
          product_id: selectedProductId,
          quantity: parseFloat(quantity),
          reference_folio: folio || null,
          notes: notes || null,
        });
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al procesar el movimiento en inventario.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-card border border-slate-100 animate-in fade-in zoom-in-95">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h3 className="text-base font-bold text-slate-900">Registrar Movimiento de Inventario</h3>
            <p className="text-xs text-slate-500">Afectación en Kardex inmutable con actualización de costeo</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
        </div>

        {/* Movement Mode Selector */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl my-4 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setMovementMode('entry')}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              movementMode === 'entry' ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-600'
            }`}
          >
            <ArrowDownRight className="w-3.5 h-3.5 text-emerald-600" />
            <span>Entrada / Ajuste +</span>
          </button>
          <button
            type="button"
            onClick={() => setMovementMode('exit')}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              movementMode === 'exit' ? 'bg-white text-rose-700 shadow-sm' : 'text-slate-600'
            }`}
          >
            <ArrowUpRight className="w-3.5 h-3.5 text-rose-600" />
            <span>Salida / Merma -</span>
          </button>
          <button
            type="button"
            onClick={() => setMovementMode('transfer')}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              movementMode === 'transfer' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600'
            }`}
          >
            <ArrowRightLeft className="w-3.5 h-3.5 text-blue-600" />
            <span>Traspaso</span>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Artículo
            </label>
            <select
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              required
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
            >
              {products.map((p) => (
                <option key={`${p.warehouse_id}-${p.product_id}`} value={p.product_id}>
                  {p.product_name} (SKU: {p.sku}) • Exist: {Number(p.physical_stock).toFixed(2)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                {movementMode === 'transfer' ? 'Almacén Origen' : 'Almacén'}
              </label>
              <input
                type="text"
                readOnly
                value={preselectedProduct?.warehouse_name || 'Almacén General'}
                className="w-full px-3.5 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-xs text-slate-600 font-semibold"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Cantidad
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold"
              />
            </div>
          </div>

          {movementMode === 'entry' && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Costo Unitario de Entrada ($ MXN)
              </label>
              <input
                type="number"
                step="0.0001"
                min="0"
                required
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Folio de Referencia (Opcional)
            </label>
            <input
              type="text"
              value={folio}
              onChange={(e) => setFolio(e.target.value)}
              placeholder="ej. AJU-001 o FAC-129"
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Notas / Justificación del Movimiento
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Motivo del ajuste, inventario físico o recepción..."
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
            ></textarea>
          </div>

          <div className="pt-4 flex items-center justify-end gap-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 disabled:opacity-50"
            >
              {loading ? 'Afectando Kardex...' : 'Aplicar Movimiento'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
