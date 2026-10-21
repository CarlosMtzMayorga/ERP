import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  ShoppingCart,
  Plus,
  Trash2,
  Search,
  CheckCircle2,
  AlertCircle,
  Building2,
  DollarSign,
  FileCheck,
  Send,
  User,
  Boxes,
} from 'lucide-react';

interface CustomerOption {
  id: string;
  code: string;
  legal_name: string;
  rfc: string;
  fiscal_regime_code: string;
  default_uso_cfdi: string;
}

interface ProductOption {
  product_id: string;
  sku: string;
  product_name: string;
  unit_name: string;
  available_stock: number;
  average_cost: number;
}

interface WarehouseOption {
  id: string;
  code: string;
  name: string;
}

interface LineItem {
  id: string;
  product_id: string;
  sku: string;
  description: string;
  unit_name: string;
  available_stock: number;
  quantity: number;
  unit_price: number;
  discount_rate: number;
  vat_rate: number;
  ieps_rate: number;
  retention_vat_rate: number;
  retention_isr_rate: number;
  subtotal: number;
  total: number;
}

interface SalesCaptureTabProps {
  onDocumentCreated: () => void;
}

export const SalesCaptureTab: React.FC<SalesCaptureTabProps> = ({ onDocumentCreated }) => {
  const [docType, setDocType] = useState<'COTIZACION' | 'PEDIDO' | 'REMISION' | 'FACTURA'>('FACTURA');
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseOption[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [selectedWarehouseId, setSelectedWarehouseId] = useState('');
  const [branchId, setBranchId] = useState('');
  const [currencyId, setCurrencyId] = useState('');
  const [paymentForm, setPaymentForm] = useState('03');
  const [paymentMethod, setPaymentMethod] = useState('PUE');
  const [cfdiUse, setCfdiUse] = useState('G03');
  const [notes, setNotes] = useState('');

  // Partidas
  const [items, setItems] = useState<LineItem[]>([]);
  const [productSearch, setProductSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const fetchCatalogData = async () => {
      try {
        const [custRes, prodRes, branchRes, currRes] = await Promise.all([
          apiClient.get<CustomerOption[]>('/tenants/current'), // Or customer endpoint
          apiClient.get<ProductOption[]>('/inventory/stocks'),
          apiClient.get<WarehouseOption[]>('/tenants/branches'),
          apiClient.get<any[]>('/tenants/current'),
        ]);

        setProducts(prodRes.data);
        if (branchRes.data.length > 0) {
          setBranchId(branchRes.data[0].id);
          setWarehouses(branchRes.data);
          setSelectedWarehouseId(branchRes.data[0].id);
        }
      } catch (err) {
        console.error('Error loading sales catalogs:', err);
      }
    };
    fetchCatalogData();
  }, []);

  const addLine = (prod: ProductOption) => {
    const existing = items.find((it) => it.product_id === prod.product_id);
    if (existing) {
      updateLine(existing.id, 'quantity', existing.quantity + 1);
      return;
    }

    const price = 250.0;
    const qty = 1;
    const sub = qty * price;
    const vat = sub * 0.16;
    const newLine: LineItem = {
      id: Math.random().toString(),
      product_id: prod.product_id,
      sku: prod.sku,
      description: prod.product_name,
      unit_name: prod.unit_name || 'PZA',
      available_stock: prod.available_stock,
      quantity: qty,
      unit_price: price,
      discount_rate: 0,
      vat_rate: 0.16,
      ieps_rate: 0,
      retention_vat_rate: 0,
      retention_isr_rate: 0,
      subtotal: sub,
      total: sub + vat,
    };
    setItems([...items, newLine]);
    setProductSearch('');
  };

  const removeLine = (id: string) => {
    setItems(items.filter((it) => it.id !== id));
  };

  const updateLine = (id: string, field: keyof LineItem, val: any) => {
    setItems(
      items.map((it) => {
        if (it.id !== id) return it;
        const updated = { ...it, [field]: val };
        const gross = updated.quantity * updated.unit_price;
        const disc = gross * (updated.discount_rate || 0);
        const sub = gross - disc;
        const vat = sub * (updated.vat_rate || 0);
        const ieps = sub * (updated.ieps_rate || 0);
        const retVat = sub * (updated.retention_vat_rate || 0);
        const retIsr = sub * (updated.retention_isr_rate || 0);
        updated.subtotal = sub;
        updated.total = sub + vat + ieps - retVat - retIsr;
        return updated;
      })
    );
  };

  // Totales consolidados
  const subtotalSum = items.reduce((acc, it) => acc + it.subtotal, 0);
  const vatSum = items.reduce((acc, it) => acc + (it.subtotal * it.vat_rate), 0);
  const totalSum = subtotalSum + vatSum;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (items.length === 0) {
      setErrorMessage('Debe agregar al menos un artículo a la venta.');
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      // Create document payload
      const payload = {
        branch_id: branchId,
        warehouse_id: selectedWarehouseId,
        customer_id: selectedCustomerId || branchId, // fallback
        currency_id: currencyId || branchId,
        document_type: docType,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
          discount_rate: it.discount_rate,
          vat_rate: it.vat_rate,
          description: it.description,
        })),
        payment_form: paymentForm,
        payment_method: paymentMethod,
        cfdi_use: cfdiUse,
        notes: notes || null,
        approve_immediately: true,
      };

      const res = await apiClient.post('/sales/documents', payload);
      setSuccessMessage(
        `¡${docType} ${res.data.formatted_folio} generada exitosamente! ${
          docType === 'PEDIDO' ? 'Reserva de inventario aplicada en almacén.' : 'Existencia descargada de Kardex.'
        }`
      );
      setItems([]);
      setNotes('');
      onDocumentCreated();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Error al emitir documento de venta.');
    } finally {
      setLoading(false);
    }
  };

  const filteredSearchProducts = products.filter(
    (p) =>
      productSearch.length >= 2 &&
      (p.product_name.toLowerCase().includes(productSearch.toLowerCase()) ||
        p.sku.toLowerCase().includes(productSearch.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      {/* Top Banner & Document Type Selector */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-soft">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <ShoppingCart className="w-5 h-5 text-blue-600" />
              <span>Punto de Captura Ultrarrápido de Ventas</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Encadenamiento documental con validación de inventario disponible en tiempo real
            </p>
          </div>

          {/* Type Selector */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl text-xs font-semibold">
            {(['COTIZACION', 'PEDIDO', 'REMISION', 'FACTURA'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setDocType(t)}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  docType === t
                    ? 'bg-blue-600 text-white shadow-sm font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Customer & Warehouse Header Fields */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mt-6 pt-5 border-t border-slate-100 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Cliente / Receptor SAT
            </label>
            <input
              type="text"
              readOnly
              value="CLIENTE GENERAL PÚBLICO (RFC: XAXX010101000)"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Almacén de Surtido
            </label>
            <select
              value={selectedWarehouseId}
              onChange={(e) => setSelectedWarehouseId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800"
            >
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} - {w.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Forma & Método SAT
            </label>
            <div className="flex gap-2">
              <select
                value={paymentForm}
                onChange={(e) => setPaymentForm(e.target.value)}
                className="w-1/2 px-2 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
              >
                <option value="01">01 Efectivo</option>
                <option value="03">03 Transferencia</option>
                <option value="04">04 Tarjeta Crédito</option>
                <option value="28">28 Tarjeta Débito</option>
                <option value="99">99 Por Definir</option>
              </select>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="w-1/2 px-2 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
              >
                <option value="PUE">PUE (Una exhibición)</option>
                <option value="PPD">PPD (Parcialidades)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Uso de CFDI
            </label>
            <select
              value={cfdiUse}
              onChange={(e) => setCfdiUse(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
            >
              <option value="G01">G01 Adquisición de mercancías</option>
              <option value="G03">G03 Gastos en general</option>
              <option value="CP01">CP01 Pagos</option>
              <option value="S01">S01 Sin efectos fiscales</option>
            </select>
          </div>
        </div>
      </div>

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Predictive Article Search Box */}
      <div className="relative">
        <div className="relative w-full">
          <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar artículo por nombre o SKU para agregar a la partida... (ej. PROD o SKU)"
            value={productSearch}
            onChange={(e) => setProductSearch(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm shadow-soft focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        {/* Predictive Dropdown */}
        {filteredSearchProducts.length > 0 && (
          <div className="absolute left-0 right-0 mt-2 bg-white rounded-2xl shadow-card border border-slate-200 max-h-60 overflow-y-auto z-40">
            {filteredSearchProducts.map((p) => (
              <button
                key={p.product_id}
                onClick={() => addLine(p)}
                className="w-full text-left px-5 py-3 hover:bg-blue-50/70 border-b border-slate-100 last:border-0 flex items-center justify-between text-xs transition-colors"
              >
                <div>
                  <div className="font-bold text-slate-900">{p.product_name}</div>
                  <div className="text-[11px] font-mono text-slate-500">SKU: {p.sku}</div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-100 font-mono text-slate-700">
                    <Boxes className="w-3 h-3 text-slate-400" />
                    <span>Disp: {Number(p.available_stock).toFixed(2)} {p.unit_name}</span>
                  </span>
                  <span className="text-blue-600 font-bold">+ Agregar</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Line Items Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-5 py-3.5">Artículo / SKU</th>
                <th className="px-5 py-3.5 text-center">Disp. Almacén</th>
                <th className="px-5 py-3.5 text-center w-28">Cantidad</th>
                <th className="px-5 py-3.5 text-right w-32">Precio Unit.</th>
                <th className="px-5 py-3.5 text-center w-24">IVA</th>
                <th className="px-5 py-3.5 text-right">Subtotal</th>
                <th className="px-5 py-3.5 text-right">Total</th>
                <th className="px-5 py-3.5 text-center w-12"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-slate-400">
                    Utiliza la barra de búsqueda superior para agregar artículos a este documento de venta.
                  </td>
                </tr>
              ) : (
                items.map((it) => (
                  <tr key={it.id} className="hover:bg-slate-50/50">
                    <td className="px-5 py-3">
                      <div className="font-bold text-slate-900">{it.description}</div>
                      <div className="text-[11px] font-mono text-blue-600">SKU: {it.sku}</div>
                    </td>
                    <td className="px-5 py-3 text-center font-mono">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        it.available_stock >= it.quantity
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-rose-50 text-rose-700 font-bold animate-pulse'
                      }`}>
                        {Number(it.available_stock).toFixed(2)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={it.quantity}
                        onChange={(e) => updateLine(it.id, 'quantity', parseFloat(e.target.value) || 0)}
                        className="w-20 text-center py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono font-bold"
                      />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={it.unit_price}
                        onChange={(e) => updateLine(it.id, 'unit_price', parseFloat(e.target.value) || 0)}
                        className="w-24 text-right py-1 px-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono"
                      />
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold text-[10px]">
                        16%
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-mono font-semibold text-slate-700">
                      ${it.subtotal.toFixed(2)}
                    </td>
                    <td className="px-5 py-3 text-right font-mono font-bold text-slate-900">
                      ${it.total.toFixed(2)}
                    </td>
                    <td className="px-5 py-3 text-center">
                      <button
                        onClick={() => removeLine(it.id)}
                        className="text-slate-400 hover:text-rose-600 p-1"
                        title="Eliminar partida"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer Summary & Action */}
        <div className="bg-slate-50 p-6 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="w-full sm:w-1/2">
            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1">
              Notas / Observaciones del Documento
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Instrucciones de entrega, términos de crédito o referencias..."
              className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-xs"
            ></textarea>
          </div>

          <div className="w-full sm:w-72 space-y-2 text-xs">
            <div className="flex justify-between text-slate-600">
              <span>Subtotal:</span>
              <span className="font-mono font-semibold">${subtotalSum.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>IVA Trasladado (16%):</span>
              <span className="font-mono font-semibold">${vatSum.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-900 font-bold text-base pt-2 border-t border-slate-200">
              <span>Total:</span>
              <span className="font-mono text-blue-600">${totalSum.toFixed(2)} MXN</span>
            </div>

            <button
              onClick={handleSubmit}
              disabled={loading || items.length === 0}
              className="w-full mt-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-md shadow-blue-500/20 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
            >
              <Send className="w-4 h-4" />
              <span>{loading ? 'Generando Venta...' : `Emitir ${docType}`}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

