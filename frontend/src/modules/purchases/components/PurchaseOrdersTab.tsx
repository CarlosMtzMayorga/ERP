import React, { useState } from 'react';
import { PurchaseDocument } from '../types';
import {
  Plus,
  Search,
  CheckCircle,
  Clock,
  Eye,
  FileCheck2,
  PackagePlus,
  X,
  PlusCircle,
  Trash2,
} from 'lucide-react';

interface Props {
  orders: PurchaseDocument[];
  suppliers: any[];
  products: any[];
  branches: any[];
  warehouses: any[];
  currencies: any[];
  onCreateOrder: (payload: any) => Promise<void>;
  onAuthorizeOrder: (orderId: string) => Promise<void>;
  onSelectForReception: (order: PurchaseDocument) => void;
  showCreateModal: boolean;
  setShowCreateModal: (show: boolean) => void;
}

export const PurchaseOrdersTab: React.FC<Props> = ({
  orders,
  suppliers,
  products,
  branches,
  warehouses,
  currencies,
  onCreateOrder,
  onAuthorizeOrder,
  onSelectForReception,
  showCreateModal,
  setShowCreateModal,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedOrder, setSelectedOrder] = useState<PurchaseDocument | null>(null);

  // Form state for creating new PO
  const [supplierId, setSupplierId] = useState('');
  const [branchId, setBranchId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [currencyId, setCurrencyId] = useState('');
  const [freightTotal, setFreightTotal] = useState<number>(0);
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<
    Array<{
      product_id: string;
      quantity: number;
      unit_cost: number;
      discount_rate: number;
    }>
  >([
    { product_id: '', quantity: 1, unit_cost: 0, discount_rate: 0 }
  ]);
  const [submitting, setSubmitting] = useState(false);

  const filteredOrders = orders.filter((o) => {
    const matchesSearch =
      o.formatted_folio.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (o.supplier_name && o.supplier_name.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesStatus = statusFilter === 'ALL' || o.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleAddItemRow = () => {
    setItems([...items, { product_id: '', quantity: 1, unit_cost: 0, discount_rate: 0 }]);
  };

  const handleRemoveItemRow = (index: number) => {
    if (items.length > 1) {
      setItems(items.filter((_, i) => i !== index));
    }
  };

  const handleItemChange = (index: number, field: string, value: any) => {
    const updated = [...items];
    (updated[index] as any)[field] = value;

    // Si cambia el producto, auto-asignar su costo o precio
    if (field === 'product_id') {
      const prod = products.find((p) => p.id === value);
      if (prod) {
        updated[index].unit_cost = Number(prod.last_cost || prod.base_price || 0);
      }
    }
    setItems(updated);
  };

  const handleSubmitPO = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supplierId || !branchId || !warehouseId || !currencyId) {
      alert('Por favor complete los datos obligatorios del encabezado.');
      return;
    }
    const validItems = items.filter((it) => it.product_id && it.quantity > 0);
    if (validItems.length === 0) {
      alert('Agregue al menos un artículo válido a la orden.');
      return;
    }

    setSubmitting(true);
    try {
      await onCreateOrder({
        supplier_id: supplierId,
        branch_id: branchId,
        warehouse_id: warehouseId,
        currency_id: currencyId,
        freight_total: Number(freightTotal) || 0,
        notes,
        items: validItems.map((it) => ({
          product_id: it.product_id,
          quantity: Number(it.quantity),
          unit_cost: Number(it.unit_cost),
          discount_rate: Number(it.discount_rate) / 100 || 0,
        })),
      });
      setShowCreateModal(false);
      // Reset form
      setItems([{ product_id: '', quantity: 1, unit_cost: 0, discount_rate: 0 }]);
      setFreightTotal(0);
      setNotes('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al crear la orden de compra.');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'BORRADOR':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">Borrador</span>;
      case 'AUTORIZADA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">Autorizada</span>;
      case 'PARCIALMENTE_RECIBIDA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">Parcial (Backorder)</span>;
      case 'RECIBIDA':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">Completamente Recibida</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-100 shadow-sm">
        <div className="flex items-center space-x-3 flex-1">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar por folio o proveedor..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 focus:outline-none"
          >
            <option value="ALL">Todos los Estados</option>
            <option value="BORRADOR">Borrador</option>
            <option value="AUTORIZADA">Autorizada</option>
            <option value="PARCIALMENTE_RECIBIDA">Parcialmente Recibida</option>
            <option value="RECIBIDA">Recibida</option>
          </select>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center justify-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4 mr-1.5" /> Nueva Orden de Compra
        </button>
      </div>

      {/* Orders Table */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-3 px-4">Folio OC</th>
                <th className="py-3 px-4">Proveedor</th>
                <th className="py-3 px-4">Fecha Emisión</th>
                <th className="py-3 px-4 text-center">Partidas</th>
                <th className="py-3 px-4 text-right">Subtotal</th>
                <th className="py-3 px-4 text-right">Flete</th>
                <th className="py-3 px-4 text-right">Total</th>
                <th className="py-3 px-4 text-center">Estado</th>
                <th className="py-3 px-4 text-center">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredOrders.length > 0 ? (
                filteredOrders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-900">{ord.formatted_folio}</td>
                    <td className="py-3 px-4 font-medium text-slate-700">
                      {ord.supplier_name || 'Proveedor'}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {new Date(ord.issue_date).toLocaleDateString('es-MX')}
                    </td>
                    <td className="py-3 px-4 text-center font-bold text-slate-600">
                      {ord.items.length}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-700">
                      ${ord.subtotal.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-500">
                      ${(ord.freight_total || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right font-extrabold text-slate-900">
                      ${ord.total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-center">{getStatusBadge(ord.status)}</td>
                    <td className="py-3 px-4 text-center space-x-1.5">
                      <button
                        onClick={() => setSelectedOrder(ord)}
                        className="p-1.5 text-slate-500 hover:text-blue-600 rounded-lg hover:bg-slate-100"
                        title="Ver detalle"
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      {ord.status === 'BORRADOR' && (
                        <button
                          onClick={() => onAuthorizeOrder(ord.id)}
                          className="px-2 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg font-bold text-[11px] inline-flex items-center"
                          title="Autorizar orden para surtido"
                        >
                          <CheckCircle className="w-3.5 h-3.5 mr-1" /> Autorizar
                        </button>
                      )}

                      {(ord.status === 'AUTORIZADA' || ord.status === 'PARCIALMENTE_RECIBIDA') && (
                        <button
                          onClick={() => onSelectForReception(ord)}
                          className="px-2 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg font-bold text-[11px] inline-flex items-center"
                          title="Pasar a recepción de almacén"
                        >
                          <PackagePlus className="w-3.5 h-3.5 mr-1" /> Recibir
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="py-10 text-center text-slate-400">
                    No se encontraron órdenes de compra registradas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Create Purchase Order */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-white rounded-3xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 sm:p-8 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
              <div>
                <h3 className="text-lg font-extrabold text-slate-900">Nueva Orden de Compra (OC)</h3>
                <p className="text-xs text-slate-500">Cree un pedido formal de aprovisionamiento a proveedor.</p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-xl hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmitPO} className="space-y-6">
              {/* Header Fields */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Proveedor *</label>
                  <select
                    required
                    value={supplierId}
                    onChange={(e) => setSupplierId(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="">Seleccione proveedor...</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.legal_name} ({s.rfc})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Sucursal *</label>
                  <select
                    required
                    value={branchId}
                    onChange={(e) => setBranchId(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="">Seleccione sucursal...</option>
                    {branches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Almacén Destino *</label>
                  <select
                    required
                    value={warehouseId}
                    onChange={(e) => setWarehouseId(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="">Seleccione almacén...</option>
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Moneda *</label>
                  <select
                    required
                    value={currencyId}
                    onChange={(e) => setCurrencyId(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="">Seleccione moneda...</option>
                    {currencies.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code} - {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Items Grid */}
              <div className="border border-slate-200 rounded-2xl p-4 bg-slate-50/50 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Partidas de la Orden</h4>
                  <button
                    type="button"
                    onClick={handleAddItemRow}
                    className="inline-flex items-center text-xs font-bold text-blue-600 hover:text-blue-700"
                  >
                    <PlusCircle className="w-4 h-4 mr-1" /> Agregar Artículo
                  </button>
                </div>

                <div className="space-y-2">
                  {items.map((it, idx) => (
                    <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-white p-2.5 rounded-xl border border-slate-100 shadow-2xs">
                      <div className="col-span-12 sm:col-span-5">
                        <select
                          required
                          value={it.product_id}
                          onChange={(e) => handleItemChange(idx, 'product_id', e.target.value)}
                          className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                        >
                          <option value="">Seleccionar artículo...</option>
                          {products.map((p) => (
                            <option key={p.id} value={p.id}>
                              [{p.sku}] {p.name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="col-span-4 sm:col-span-2">
                        <input
                          type="number"
                          min="0.0001"
                          step="any"
                          required
                          placeholder="Cantidad"
                          value={it.quantity}
                          onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                          className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-right"
                        />
                      </div>

                      <div className="col-span-4 sm:col-span-2">
                        <input
                          type="number"
                          min="0"
                          step="any"
                          required
                          placeholder="Costo Unitario"
                          value={it.unit_cost}
                          onChange={(e) => handleItemChange(idx, 'unit_cost', e.target.value)}
                          className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-right"
                        />
                      </div>

                      <div className="col-span-3 sm:col-span-2">
                        <div className="relative">
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="any"
                            placeholder="Desc %"
                            value={it.discount_rate}
                            onChange={(e) => handleItemChange(idx, 'discount_rate', e.target.value)}
                            className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-right pr-6"
                          />
                          <span className="absolute right-2 top-2 text-xs text-slate-400">%</span>
                        </div>
                      </div>

                      <div className="col-span-1 text-center">
                        <button
                          type="button"
                          onClick={() => handleRemoveItemRow(idx)}
                          disabled={items.length === 1}
                          className="p-1.5 text-slate-400 hover:text-rose-600 disabled:opacity-30 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Freight & Notes */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Flete Total a Prorratear ($)</label>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={freightTotal}
                    onChange={(e) => setFreightTotal(Number(e.target.value))}
                    placeholder="0.00"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-right focus:ring-2 focus:ring-blue-500/20"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">Se prorratea en el costo unitario de los artículos en la recepción.</p>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Notas / Observaciones</label>
                  <input
                    type="text"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Instrucciones especiales de entrega..."
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                  />
                </div>
              </div>

              {/* Submit Buttons */}
              <div className="flex justify-end space-x-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm disabled:opacity-50"
                >
                  {submitting ? 'Guardando...' : 'Guardar Orden de Compra'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: View Order Details */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-3xl shadow-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6 sm:p-8 animate-in fade-in">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
              <div>
                <span className="text-xs font-bold text-blue-600 uppercase">Orden de Compra</span>
                <h3 className="text-xl font-extrabold text-slate-900">{selectedOrder.formatted_folio}</h3>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-xl hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded-xl">
                <div>
                  <span className="text-slate-400 font-medium">Proveedor:</span>
                  <p className="font-bold text-slate-800">{selectedOrder.supplier_name}</p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Fecha:</span>
                  <p className="font-bold text-slate-800">
                    {new Date(selectedOrder.issue_date).toLocaleDateString('es-MX')}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Estado:</span>
                  <div className="mt-0.5">{getStatusBadge(selectedOrder.status)}</div>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-slate-800 mb-2">Partidas</h4>
                <div className="border border-slate-100 rounded-xl overflow-hidden">
                  <table className="w-full text-left">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                      <tr>
                        <th className="py-2 px-3">Artículo</th>
                        <th className="py-2 px-3 text-right">Pedida</th>
                        <th className="py-2 px-3 text-right">Recibida</th>
                        <th className="py-2 px-3 text-right">Costo Unit.</th>
                        <th className="py-2 px-3 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedOrder.items.map((it) => (
                        <tr key={it.id}>
                          <td className="py-2 px-3">
                            <span className="font-bold text-slate-900">[{it.sku}]</span> {it.description}
                          </td>
                          <td className="py-2 px-3 text-right font-medium">{it.quantity_ordered}</td>
                          <td className="py-2 px-3 text-right font-bold text-emerald-600">{it.quantity_received}</td>
                          <td className="py-2 px-3 text-right font-medium">${it.unit_cost.toFixed(2)}</td>
                          <td className="py-2 px-3 text-right font-bold text-slate-900">${it.total.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <div className="w-64 space-y-1 text-right">
                  <div className="flex justify-between text-slate-500">
                    <span>Subtotal:</span>
                    <span>${selectedOrder.subtotal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-slate-500">
                    <span>IVA (16%):</span>
                    <span>${selectedOrder.tax_iva_total.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-slate-500">
                    <span>Flete:</span>
                    <span>${selectedOrder.freight_total.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm font-extrabold text-slate-900 border-t border-slate-200 pt-1">
                    <span>Total:</span>
                    <span>${selectedOrder.total.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

