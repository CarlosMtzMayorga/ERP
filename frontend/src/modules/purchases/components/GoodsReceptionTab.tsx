import React, { useState, useEffect, useRef } from 'react';
import { PurchaseDocument } from '../types';
import {
  PackageCheck,
  Barcode,
  AlertTriangle,
  CheckCircle,
  Truck,
  ArrowRight,
  Info,
  Layers,
} from 'lucide-react';

interface Props {
  activeOrders: PurchaseDocument[];
  selectedPO: PurchaseDocument | null;
  onSelectPO: (po: PurchaseDocument | null) => void;
  warehouses: any[];
  branches: any[];
  onConfirmReception: (payload: any) => Promise<void>;
}

interface ReceptionLine {
  source_item_id?: string;
  product_id: string;
  sku: string;
  description: string;
  quantity_ordered: number;
  quantity_already_received: number;
  quantity_now: number;
  unit_cost: number;
}

export const GoodsReceptionTab: React.FC<Props> = ({
  activeOrders,
  selectedPO,
  onSelectPO,
  warehouses,
  branches,
  onConfirmReception,
}) => {
  const [receptionLines, setReceptionLines] = useState<ReceptionLine[]>([]);
  const [freightTotal, setFreightTotal] = useState<number>(0);
  const [warehouseId, setWarehouseId] = useState<string>('');
  const [branchId, setBranchId] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [barcodeInput, setBarcodeInput] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const barcodeInputRef = useRef<HTMLInputElement>(null);

  // Initialize lines when selectedPO changes
  useEffect(() => {
    if (selectedPO) {
      setWarehouseId(selectedPO.warehouse_id);
      setBranchId(selectedPO.branch_id);
      setFreightTotal(selectedPO.freight_total || 0);

      const lines: ReceptionLine[] = selectedPO.items.map((it) => {
        const remaining = Math.max(0, it.quantity_ordered - it.quantity_received);
        return {
          source_item_id: it.id,
          product_id: it.product_id,
          sku: it.sku,
          description: it.description,
          quantity_ordered: it.quantity_ordered,
          quantity_already_received: it.quantity_received,
          quantity_now: remaining, // default to remaining
          unit_cost: it.unit_cost,
        };
      });
      setReceptionLines(lines);
    } else {
      setReceptionLines([]);
    }
  }, [selectedPO]);

  // Handle barcode scanning match
  const handleBarcodeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!barcodeInput.trim()) return;

    const term = barcodeInput.trim().toUpperCase();
    const lineIndex = receptionLines.findIndex(
      (l) => l.sku.toUpperCase() === term || l.description.toUpperCase().includes(term)
    );

    if (lineIndex >= 0) {
      const updated = [...receptionLines];
      updated[lineIndex].quantity_now = Number(updated[lineIndex].quantity_now || 0) + 1;
      setReceptionLines(updated);
      setBarcodeInput('');
    } else {
      alert(`No se encontró ningún artículo en la orden con código '${term}'.`);
    }
  };

  const handleQuantityNowChange = (index: number, val: number) => {
    const updated = [...receptionLines];
    updated[index].quantity_now = Math.max(0, val);
    setReceptionLines(updated);
  };

  const handleProcessReception = async () => {
    if (!selectedPO) {
      alert('Seleccione una Orden de Compra para recibir.');
      return;
    }
    const linesToReceive = receptionLines.filter((l) => l.quantity_now > 0);
    if (linesToReceive.length === 0) {
      alert('Declare al menos una cantidad mayor a cero para recibir.');
      return;
    }

    setIsSubmitting(true);
    try {
      await onConfirmReception({
        branch_id: branchId || selectedPO.branch_id,
        warehouse_id: warehouseId || selectedPO.warehouse_id,
        supplier_id: selectedPO.supplier_id,
        currency_id: selectedPO.currency_id,
        purchase_order_id: selectedPO.id,
        freight_total: Number(freightTotal) || 0,
        notes: notes || `Recepción en almacén para OC ${selectedPO.formatted_folio}`,
        items: linesToReceive.map((l) => ({
          product_id: l.product_id,
          quantity_received: Number(l.quantity_now),
          unit_cost: Number(l.unit_cost),
          source_item_id: l.source_item_id,
        })),
      });
      alert('¡Mercancía recibida exitosamente en almacén! Se actualizó el Kardex y las capas de costeo.');
      onSelectPO(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al procesar la recepción de mercancía.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Selector */}
      <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 max-w-md">
          <label className="block text-xs font-bold text-slate-700 mb-1">
            Seleccionar Orden de Compra a Surtir *
          </label>
          <select
            value={selectedPO?.id || ''}
            onChange={(e) => {
              const po = activeOrders.find((o) => o.id === e.target.value) || null;
              onSelectPO(po);
            }}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold focus:ring-2 focus:ring-emerald-500/20"
          >
            <option value="">-- Seleccionar Orden de Compra autorizada o parcial --</option>
            {activeOrders.map((po) => (
              <option key={po.id} value={po.id}>
                {po.formatted_folio} - {po.supplier_name} (${po.total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}) [{po.status}]
              </option>
            ))}
          </select>
        </div>

        {selectedPO && (
          <div className="flex items-center space-x-3 text-xs bg-emerald-50 text-emerald-800 p-3 rounded-xl border border-emerald-200">
            <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <div>
              <p className="font-bold">OC: {selectedPO.formatted_folio}</p>
              <p className="text-[11px] text-emerald-700">Proveedor: {selectedPO.supplier_name}</p>
            </div>
          </div>
        )}
      </div>

      {selectedPO ? (
        <div className="space-y-6">
          {/* Barcode Scanner Bar */}
          <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white p-4 rounded-2xl shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-emerald-500/20 text-emerald-400 rounded-xl">
                <Barcode className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-sm font-bold">Escaneo de Códigos de Barra</h4>
                <p className="text-xs text-slate-300">Escanee o escriba el SKU/código para sumar piezas recibidas automáticamente.</p>
              </div>
            </div>

            <form onSubmit={handleBarcodeSubmit} className="flex w-full sm:w-auto space-x-2">
              <input
                ref={barcodeInputRef}
                type="text"
                placeholder="Escanee código de barras..."
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                className="w-full sm:w-64 px-3 py-2 bg-white/10 border border-white/20 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-400"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors"
              >
                Sumar
              </button>
            </form>
          </div>

          {/* Reception Grid with Discrepancy Highlighting */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center">
                <PackageCheck className="w-4 h-4 mr-1.5 text-emerald-600" />
                Validación de Partidas Recibidas vs. Pedidas
              </h4>
              <span className="text-[11px] text-slate-400 flex items-center">
                <Info className="w-3.5 h-3.5 mr-1" /> Las discrepancias mayores a lo pedido se resaltan en rojo
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-4">Artículo / SKU</th>
                    <th className="py-3 px-4 text-right">Cant. Pedida</th>
                    <th className="py-3 px-4 text-right">Ya Recibida</th>
                    <th className="py-3 px-4 text-right">Pendiente</th>
                    <th className="py-3 px-4 text-center w-36">Recibir Ahora</th>
                    <th className="py-3 px-4 text-right">Costo Unit.</th>
                    <th className="py-3 px-4 text-center">Estatus Físico</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {receptionLines.map((line, idx) => {
                    const totalReceiving = line.quantity_already_received + Number(line.quantity_now || 0);
                    const isExceeded = totalReceiving > line.quantity_ordered;
                    const isCompleted = totalReceiving === line.quantity_ordered;
                    const isPartial = totalReceiving < line.quantity_ordered && totalReceiving > 0;
                    const pending = Math.max(0, line.quantity_ordered - line.quantity_already_received);

                    return (
                      <tr
                        key={idx}
                        className={`transition-colors ${
                          isExceeded
                            ? 'bg-rose-50/70 border-l-4 border-l-rose-500'
                            : isCompleted
                            ? 'bg-emerald-50/40'
                            : 'hover:bg-slate-50/50'
                        }`}
                      >
                        <td className="py-3 px-4">
                          <p className="font-bold text-slate-900">[{line.sku}]</p>
                          <p className="text-slate-500 truncate max-w-xs">{line.description}</p>
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-700">
                          {line.quantity_ordered}
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-500">
                          {line.quantity_already_received}
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-slate-800">
                          {pending}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <input
                            type="number"
                            min="0"
                            step="any"
                            value={line.quantity_now}
                            onChange={(e) => handleQuantityNowChange(idx, Number(e.target.value))}
                            className={`w-28 p-2 rounded-lg text-xs font-bold text-right border ${
                              isExceeded
                                ? 'border-rose-300 bg-white text-rose-700 ring-2 ring-rose-500/20'
                                : 'border-slate-200 bg-slate-50 text-slate-900 focus:bg-white focus:ring-2 focus:ring-emerald-500/20'
                            }`}
                          />
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-700">
                          ${line.unit_cost.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {isExceeded ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-700 border border-rose-200 animate-pulse">
                              <AlertTriangle className="w-3 h-3 mr-1" /> Discrepancia (+{totalReceiving - line.quantity_ordered})
                            </span>
                          ) : isCompleted ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                              <CheckCircle className="w-3 h-3 mr-1" /> Completo
                            </span>
                          ) : isPartial ? (
                            <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
                              Parcial
                            </span>
                          ) : (
                            <span className="text-slate-400 text-[11px]">Sin surtir</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Freight Prorating and Confirm Section */}
          <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex-1 space-y-2">
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-700">
                <Truck className="w-4 h-4 text-blue-600" />
                <span>Prorrateo de Flete de Entrada ($)</span>
              </div>
              <div className="flex items-center space-x-3">
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={freightTotal}
                  onChange={(e) => setFreightTotal(Number(e.target.value))}
                  placeholder="0.00"
                  className="w-40 p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-right focus:ring-2 focus:ring-blue-500/20"
                />
                <span className="text-[11px] text-slate-500">
                  Se distribuirá matemáticamente en el costo efectivo de cada pieza recibida para el Kardex.
                </span>
              </div>
            </div>

            <button
              onClick={handleProcessReception}
              disabled={isSubmitting}
              className="w-full md:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-md shadow-emerald-500/20 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
            >
              <Layers className="w-4 h-4" />
              <span>{isSubmitting ? 'Procesando Entrada...' : 'Confirmar Entrada al Almacén (Kardex & PEPS)'}</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-dashed border-slate-200 p-12 text-center">
          <div className="w-16 h-16 bg-slate-50 text-slate-400 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <PackageCheck className="w-8 h-8" />
          </div>
          <h4 className="text-sm font-bold text-slate-800">Seleccione una Orden de Compra para Recibir</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            Elija una OC en el selector superior para cargar sus partidas, escanear códigos de barras y validar existencias físicas contra lo pedido.
          </p>
        </div>
      )}
    </div>
  );
};

