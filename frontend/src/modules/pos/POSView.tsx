import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { apiClient } from '../../api/axiosClient';
import {
  CashRegister,
  CashSession,
  CartItem,
  POSTicket,
  CorteXData
} from './types';
import { OpenSessionModal } from './components/OpenSessionModal';
import { PaymentModal } from './components/PaymentModal';
import { CorteXModal } from './components/CorteXModal';
import { CorteZModal } from './components/CorteZModal';
import { CashMovementModal } from './components/CashMovementModal';
import { TicketReceiptModal } from './components/TicketReceiptModal';
import { GlobalInvoiceModal } from './components/GlobalInvoiceModal';
import {
  ShoppingCart,
  Barcode,
  Search,
  Plus,
  Minus,
  Trash2,
  DollarSign,
  CreditCard,
  Lock,
  FileText,
  RotateCcw,
  Receipt,
  FileCheck2,
  AlertCircle,
  CheckCircle2,
  Printer,
  Package,
  Layers,
  ArrowRightLeft
} from 'lucide-react';

interface ProductItem {
  id: string;
  sku: string;
  barcode: string;
  name: string;
  base_price: number;
  vat_rate: number;
}

export const POSView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'terminal' | 'tickets'>('terminal');

  // Registers & Session state
  const [registers, setRegisters] = useState<CashRegister[]>([]);
  const [selectedRegisterId, setSelectedRegisterId] = useState<string>('');
  const [activeSession, setActiveSession] = useState<CashSession | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(true);

  // Products & Cart
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [barcodeInput, setBarcodeInput] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const barcodeInputRef = useRef<HTMLInputElement>(null);

  // Tickets History
  const [tickets, setTickets] = useState<POSTicket[]>([]);
  const [isLoadingTickets, setIsLoadingTickets] = useState<boolean>(false);

  // Modals state
  const [showOpenSessionModal, setShowOpenSessionModal] = useState<boolean>(false);
  const [showPaymentModal, setShowPaymentModal] = useState<boolean>(false);
  const [showCorteXModal, setShowCorteXModal] = useState<boolean>(false);
  const [corteXData, setCorteXData] = useState<CorteXData | null>(null);
  const [showCorteZModal, setShowCorteZModal] = useState<boolean>(false);
  const [showMovementModal, setShowMovementModal] = useState<boolean>(false);
  const [showGlobalInvoiceModal, setShowGlobalInvoiceModal] = useState<boolean>(false);
  const [receiptTicket, setReceiptTicket] = useState<POSTicket | null>(null);

  // Status & notifications
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  useEffect(() => {
    loadRegistersAndSession();
    loadProducts();
  }, []);

  useEffect(() => {
    if (activeTab === 'tickets') {
      loadTickets();
    }
  }, [activeTab]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadRegistersAndSession = async () => {
    setIsLoadingSession(true);
    try {
      const regRes = await apiClient.get<CashRegister[]>('/pos/registers');
      const list = regRes.data || [];
      setRegisters(list);

      if (list.length > 0) {
        const reg = list[0];
        setSelectedRegisterId(reg.id);
        await checkActiveSession(reg.id);
      } else {
        // Si no existen cajas registradoras, crear una por defecto
        const branchId = localStorage.getItem('erp_branch_id');
        // fallback
        if (branchId) {
          try {
            const newReg = await apiClient.post('/pos/registers', {
              branch_id: branchId,
              warehouse_id: branchId, // fallback
              code: 'CAJA-01',
              name: 'Caja Principal Mostrador',
            });
            setRegisters([newReg.data]);
            setSelectedRegisterId(newReg.data.id);
            await checkActiveSession(newReg.data.id);
          } catch (e) {
            console.error('Error auto-creating default register:', e);
          }
        }
      }
    } catch (err: any) {
      console.error('Error loading registers:', err);
    } finally {
      setIsLoadingSession(false);
    }
  };

  const checkActiveSession = async (registerId: string) => {
    try {
      const res = await apiClient.get('/pos/sessions/active', {
        params: { cash_register_id: registerId },
      });
      if (res.data.has_active_session) {
        setActiveSession(res.data.session);
        setShowOpenSessionModal(false);
      } else {
        setActiveSession(null);
        setShowOpenSessionModal(true);
      }
    } catch (err: any) {
      console.error('Error checking active session:', err);
    }
  };

  const loadProducts = async () => {
    try {
      const res = await apiClient.get('/pos/products');
      if (res.data && res.data.length > 0) {
        setProducts(res.data);
      } else {
        // Si no hay productos aún, crear demo items para pruebas en caliente
        const demo: ProductItem[] = [
          { id: 'prod-1', sku: 'REF-600', barcode: '7501055300075', name: 'Refresco Coca Cola 600ml', base_price: 25.00, vat_rate: 0.16 },
          { id: 'prod-2', sku: 'AGUA-1L', barcode: '7501055312345', name: 'Agua Purificada 1 Litro', base_price: 15.00, vat_rate: 0.16 },
          { id: 'prod-3', sku: 'PAPAS-45G', barcode: '7501011112233', name: 'Papas Fritas Sal 45g', base_price: 22.00, vat_rate: 0.16 },
          { id: 'prod-4', sku: 'GALLETAS', barcode: '7501000145678', name: 'Galletas Chocolate 120g', base_price: 28.00, vat_rate: 0.16 },
          { id: 'prod-5', sku: 'SERV-RECARGA', barcode: '7501999988776', name: 'Recarga Celular $100', base_price: 100.00, vat_rate: 0.16 },
          { id: 'prod-6', sku: 'CAFE-AMER', barcode: '7501000000001', name: 'Café Americano 12oz', base_price: 35.00, vat_rate: 0.16 },
        ];
        setProducts(demo);
      }
    } catch (err) {
      console.error('Error loading POS products:', err);
    }
  };

  const loadTickets = async () => {
    setIsLoadingTickets(true);
    try {
      const res = await apiClient.get('/pos/tickets', {
        params: { session_id: activeSession?.id },
      });
      setTickets(res.data);
    } catch (err: any) {
      console.error('Error loading tickets:', err);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  // Cart operations
  const addToCart = (product: ProductItem, qty: number = 1) => {
    setCart((prev) => {
      const existingIndex = prev.findIndex((i) => i.product_id === product.id || i.sku === product.sku);
      const grossPrice = Number(product.base_price) || 20;

      if (existingIndex >= 0) {
        const nextCart = [...prev];
        const item = nextCart[existingIndex];
        const newQty = item.quantity + qty;
        const total = newQty * grossPrice;
        const base = Math.round((total / 1.16) * 100) / 100;
        const vat = Math.round((total - base) * 100) / 100;

        nextCart[existingIndex] = {
          ...item,
          quantity: newQty,
          subtotal: base,
          vat_amount: vat,
          total: total,
        };
        return nextCart;
      } else {
        const total = qty * grossPrice;
        const base = Math.round((total / 1.16) * 100) / 100;
        const vat = Math.round((total - base) * 100) / 100;

        return [
          ...prev,
          {
            product_id: product.id,
            sku: product.sku,
            name: product.name,
            quantity: qty,
            unit_price: grossPrice,
            subtotal: base,
            vat_amount: vat,
            total: total,
          },
        ];
      }
    });

    if (barcodeInputRef.current) {
      barcodeInputRef.current.focus();
    }
  };

  const updateCartQty = (index: number, delta: number) => {
    setCart((prev) => {
      const next = [...prev];
      const item = next[index];
      const newQty = item.quantity + delta;
      if (newQty <= 0) {
        return prev.filter((_, i) => i !== index);
      }
      const total = newQty * item.unit_price;
      const base = Math.round((total / 1.16) * 100) / 100;
      const vat = Math.round((total - base) * 100) / 100;

      next[index] = {
        ...item,
        quantity: newQty,
        subtotal: base,
        vat_amount: vat,
        total: total,
      };
      return next;
    });
  };

  const removeFromCart = (index: number) => {
    setCart((prev) => prev.filter((_, i) => i !== index));
  };

  const clearCart = () => {
    setCart([]);
  };

  // Barcode / SKU scan submit
  const handleBarcodeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = barcodeInput.trim();
    if (!query) return;

    const matched = products.find(
      (p) => p.barcode === query || p.sku.toLowerCase() === query.toLowerCase()
    );

    if (matched) {
      addToCart(matched, 1);
      setBarcodeInput('');
    } else {
      setErrorMessage(`Artículo con código '${query}' no encontrado.`);
      setTimeout(() => setErrorMessage(null), 3000);
    }
  };

  // Calculations
  const cartTotal = cart.reduce((acc, it) => acc + it.total, 0);
  const cartSubtotal = cart.reduce((acc, it) => acc + it.subtotal, 0);
  const cartVat = cart.reduce((acc, it) => acc + it.vat_amount, 0);

  // Cash Session Actions
  const handleOpenSession = async (registerId: string, initialCash: number, notes?: string) => {
    setIsSubmitting(true);
    try {
      const res = await apiClient.post('/pos/sessions/open', {
        cash_register_id: registerId,
        initial_cash: initialCash,
        notes,
      });
      showToast('Turno de caja iniciado correctamente.');
      setShowOpenSessionModal(false);
      await checkActiveSession(registerId);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCashMovement = async (type: 'ENTRY' | 'WITHDRAWAL', amount: number, reason: string) => {
    if (!activeSession) return;
    setIsSubmitting(true);
    try {
      await apiClient.post(`/pos/sessions/${activeSession.id}/movement`, {
        movement_type: type,
        amount,
        reason,
      });
      showToast(`Movimiento de efectivo registrado exitosamente.`);
      await checkActiveSession(activeSession.cash_register_id);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleShowCorteX = async () => {
    if (!activeSession) return;
    try {
      const res = await apiClient.get<CorteXData>(`/pos/sessions/${activeSession.id}/corte-x`);
      setCorteXData(res.data);
      setShowCorteXModal(true);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Error al obtener Corte X');
    }
  };

  const handleConfirmCorteZ = async (declaredCash: number, declaredCard: number, notes?: string) => {
    if (!activeSession) return;
    setIsSubmitting(true);
    try {
      const res = await apiClient.post(`/pos/sessions/${activeSession.id}/corte-z`, {
        declared_cash: declaredCash,
        declared_card: declaredCard,
        notes,
      });
      setShowCorteZModal(false);
      setActiveSession(null);
      showToast('Corte Z completado. El turno de caja ha quedado cerrado.');
      setShowOpenSessionModal(true);
      return res.data;
    } finally {
      setIsSubmitting(false);
    }
  };

  // Payment checkout
  const handleConfirmPayment = async (paymentData: {
    payment_method: string;
    amount_paid: number;
    amount_cash?: number;
    amount_card?: number;
    amount_transfer?: number;
  }) => {
    if (!activeSession || cart.length === 0) return;
    setIsSubmitting(true);

    try {
      const payload = {
        session_id: activeSession.id,
        items: cart.map((it) => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
          description: it.name,
        })),
        payment_method: paymentData.payment_method,
        amount_paid: paymentData.amount_paid,
        amount_cash: paymentData.amount_cash,
        amount_card: paymentData.amount_card,
        amount_transfer: paymentData.amount_transfer,
      };

      const res = await apiClient.post('/pos/tickets', payload);
      const newTicket: POSTicket = {
        ...res.data,
        items: cart.map((it, idx) => ({
          id: `item-${idx}`,
          sku: it.sku,
          description: it.name,
          quantity: it.quantity,
          unit_price: it.unit_price,
          subtotal: it.subtotal,
          vat_amount: it.vat_amount,
          total: it.total,
          unit_cost: 0,
          total_cost: 0,
        })),
      };

      setShowPaymentModal(false);
      clearCart();
      showToast(`¡Ticket ${newTicket.folio} registrado con éxito!`);
      setReceiptTicket(newTicket);
      await checkActiveSession(activeSession.cash_register_id);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filtered products for Touch Grid
  const filteredProducts = products.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="flex flex-col h-full space-y-4 max-w-7xl mx-auto font-sans"
    >
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 right-8 z-50 bg-[#047857] text-white px-4 py-2.5 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-bold animate-in fade-in slide-in-from-top-4">
          <CheckCircle2 className="w-4 h-4" />
          <span>{toastMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="fixed top-20 right-8 z-50 bg-rose-600 text-white px-4 py-2.5 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-bold animate-in fade-in slide-in-from-top-4">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Top POS Control Bar */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700/60 p-5 flex flex-wrap items-center justify-between gap-4">
        {/* Cash Register & Status */}
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] rounded-2xl flex items-center justify-center border border-[#047857]/20">
            <Receipt className="w-6 h-6 text-[#047857]" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white tracking-tight">
                Módulo 4: Punto de Venta (POS)
              </h1>
              {activeSession ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950/70 text-[#047857] dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#047857] mr-1.5 animate-pulse"></span>
                  TURNO ABIERTO
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5"></span>
                  CAJA CERRADA
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {activeSession
                ? `Caja: ${activeSession.cash_register_name || 'CAJA-01'} | Cajero: ${activeSession.cashier_name || 'Operador'}`
                : 'Seleccione una caja y aperture un turno para operar.'}
            </p>
          </div>
        </div>

        {/* Live Shift Metrics & Buttons */}
        {activeSession ? (
          <div className="flex flex-wrap items-center gap-3">
            {/* Shift Balance Pill */}
            <div className="bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-1.5 text-xs flex items-center space-x-3">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Fondo</span>
                <span className="font-bold text-slate-700">${Number(activeSession.initial_cash).toFixed(2)}</span>
              </div>
              <div className="w-px h-6 bg-slate-200"></div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Efectivo Esperado</span>
                <span className="font-extrabold text-blue-700">${Number(activeSession.expected_cash).toFixed(2)}</span>
              </div>
              <div className="w-px h-6 bg-slate-200"></div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Tickets</span>
                <span className="font-bold text-emerald-700">{activeSession.tickets_count}</span>
              </div>
            </div>

            {/* Quick Actions */}
            <button
              onClick={() => setShowMovementModal(true)}
              className="py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition"
              title="Entradas y Retiros de Efectivo"
            >
              <ArrowRightLeft className="w-3.5 h-3.5" />
              <span>Entrada / Retiro</span>
            </button>

            <button
              onClick={handleShowCorteX}
              className="py-2 px-3 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition"
              title="Corte X (Lectura Parcial)"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Corte X</span>
            </button>

            <button
              onClick={() => setShowCorteZModal(true)}
              className="py-2 px-3 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition shadow shadow-rose-600/20"
              title="Corte Z (Cierre definitivo a ciegas)"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Corte Z</span>
            </button>

            <button
              onClick={() => setShowGlobalInvoiceModal(true)}
              className="py-2 px-3 bg-indigo-700 hover:bg-indigo-800 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition shadow shadow-indigo-700/20"
              title="Consolidación de tickets a CFDI 4.0 Global"
            >
              <FileCheck2 className="w-3.5 h-3.5" />
              <span>Factura Global</span>
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowOpenSessionModal(true)}
            className="py-2.5 px-5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-lg shadow-blue-500/25 flex items-center space-x-2 transition"
          >
            <DollarSign className="w-4 h-4" />
            <span>Abrir Turno de Caja</span>
          </button>
        )}
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab('terminal')}
          className={`py-2 px-4 text-xs font-bold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'terminal'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <ShoppingCart className="w-4 h-4" />
          <span>Terminal de Venta</span>
        </button>
        <button
          onClick={() => setActiveTab('tickets')}
          className={`py-2 px-4 text-xs font-bold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'tickets'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Receipt className="w-4 h-4" />
          <span>Historial de Tickets</span>
        </button>
      </div>

      {/* TAB 1: TERMINAL DE VENTA */}
      {activeTab === 'terminal' && (
        <div className="grid grid-cols-12 gap-5 flex-1 min-h-[550px]">
          {/* LEFT: CART & TOTALS (5 Cols) */}
          <div className="col-span-12 lg:col-span-5 bg-white rounded-2xl shadow-sm border border-slate-200 p-4 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <ShoppingCart className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Ticket Actual ({cart.length} partidas)
                  </span>
                </div>
                {cart.length > 0 && (
                  <button
                    onClick={clearCart}
                    className="text-[11px] font-semibold text-rose-600 hover:text-rose-800 flex items-center space-x-1"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>Vaciar</span>
                  </button>
                )}
              </div>

              {/* Items List */}
              <div className="divide-y divide-slate-100 max-h-[340px] overflow-y-auto mt-2 pr-1">
                {cart.length === 0 ? (
                  <div className="py-16 text-center text-slate-400">
                    <Package className="w-12 h-12 mx-auto text-slate-300 mb-2 stroke-[1.5]" />
                    <p className="text-xs font-medium">El carrito de cobro está vacío.</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Escanee un código de barras o seleccione productos del catálogo.
                    </p>
                  </div>
                ) : (
                  cart.map((item, index) => (
                    <div key={item.product_id} className="py-2.5 flex items-center justify-between text-xs group">
                      <div className="flex-1 pr-2">
                        <span className="font-bold text-slate-900 block truncate">{item.name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {item.sku} • ${item.unit_price.toFixed(2)} c/u
                        </span>
                      </div>
                      <div className="flex items-center space-x-2">
                        {/* Quantity Adjusters */}
                        <div className="flex items-center border border-slate-200 rounded-lg bg-slate-50">
                          <button
                            onClick={() => updateCartQty(index, -1)}
                            className="p-1 hover:bg-slate-200 text-slate-600 rounded-l transition"
                          >
                            <Minus className="w-3 h-3" />
                          </button>
                          <span className="px-2 font-bold text-slate-800">{item.quantity}</span>
                          <button
                            onClick={() => updateCartQty(index, 1)}
                            className="p-1 hover:bg-slate-200 text-slate-600 rounded-r transition"
                          >
                            <Plus className="w-3 h-3" />
                          </button>
                        </div>
                        {/* Line Total */}
                        <span className="w-16 text-right font-extrabold text-slate-900">
                          ${item.total.toFixed(2)}
                        </span>
                        <button
                          onClick={() => removeFromCart(index)}
                          className="text-slate-300 hover:text-rose-600 p-1 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Bottom Totals and Checkout Button */}
            <div className="pt-4 border-t border-slate-200 space-y-3">
              <div className="space-y-1.5 text-xs text-slate-600">
                <div className="flex justify-between">
                  <span>Subtotal (Base Gravable):</span>
                  <span className="font-semibold text-slate-800">${cartSubtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>IVA Trasladado (16%):</span>
                  <span className="font-semibold text-slate-800">${cartVat.toFixed(2)}</span>
                </div>
              </div>

              {/* Total Banner */}
              <div className="bg-slate-900 rounded-xl p-4 text-white flex justify-between items-center shadow-inner">
                <div>
                  <span className="text-[10px] uppercase tracking-widest text-slate-400 font-bold block">
                    Total a Cobrar
                  </span>
                  <span className="text-xs text-slate-300">Moneda Nacional MXN</span>
                </div>
                <div className="text-3xl font-black text-emerald-400 tracking-tight">
                  ${cartTotal.toFixed(2)}
                </div>
              </div>

              {/* Cobrar Button */}
              <button
                disabled={cart.length === 0 || !activeSession}
                onClick={() => setShowPaymentModal(true)}
                className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl font-black text-sm uppercase tracking-wider shadow-lg shadow-emerald-600/25 flex items-center justify-center space-x-2 transition"
              >
                <CreditCard className="w-5 h-5" />
                <span>Cobrar Ticket (F12)</span>
              </button>
            </div>
          </div>

          {/* RIGHT: BARCODE INPUT & PRODUCT TOUCH GRID (7 Cols) */}
          <div className="col-span-12 lg:col-span-7 flex flex-col space-y-4">
            {/* Barcode & Search Input */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-3 flex gap-3">
              <form onSubmit={handleBarcodeSubmit} className="flex-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Barcode className="w-5 h-5" />
                </div>
                <input
                  ref={barcodeInputRef}
                  type="text"
                  value={barcodeInput}
                  onChange={(e) => setBarcodeInput(e.target.value)}
                  placeholder="Escanear Código de Barras o SKU (Enter)..."
                  className="w-full pl-10 pr-4 py-2.5 text-xs font-semibold rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50 focus:bg-white"
                  autoFocus
                />
              </form>
              <div className="w-1/3 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Search className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filtrar por nombre..."
                  className="w-full pl-9 pr-3 py-2.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Touch Grid */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 flex-1 flex flex-col">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center space-x-1.5">
                  <Layers className="w-4 h-4 text-blue-600" />
                  <span>Artículos de Alta Rotación</span>
                </span>
                <span className="text-[11px] text-slate-400 font-medium">
                  {filteredProducts.length} artículos disponibles
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 overflow-y-auto max-h-[460px] pr-1">
                {filteredProducts.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => addToCart(p, 1)}
                    className="p-3 rounded-xl border border-slate-200 hover:border-blue-500 hover:shadow-md bg-white text-left transition flex flex-col justify-between group active:scale-[0.98]"
                  >
                    <div>
                      <span className="text-[10px] text-slate-400 font-mono block mb-1">
                        {p.sku}
                      </span>
                      <h4 className="text-xs font-bold text-slate-900 group-hover:text-blue-600 line-clamp-2 leading-tight">
                        {p.name}
                      </h4>
                    </div>
                    <div className="pt-3 flex items-center justify-between border-t border-slate-100 mt-2">
                      <span className="text-sm font-black text-slate-900">
                        ${Number(p.base_price).toFixed(2)}
                      </span>
                      <span className="p-1 bg-blue-50 text-blue-600 rounded-lg group-hover:bg-blue-600 group-hover:text-white transition">
                        <Plus className="w-3.5 h-3.5" />
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: HISTORIAL DE TICKETS */}
      {activeTab === 'tickets' && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold text-slate-900">Tickets Emitidos en el Turno</h3>
              <p className="text-xs text-slate-500">
                Auditoría transaccional de ventas y comprobantes emitidos
              </p>
            </div>
            <button
              onClick={loadTickets}
              className="py-1.5 px-3 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-lg flex items-center space-x-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Actualizar</span>
            </button>
          </div>

          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Folio Ticket</th>
                  <th className="py-3 px-4">Fecha y Hora</th>
                  <th className="py-3 px-4">Cliente</th>
                  <th className="py-3 px-4">Forma de Pago</th>
                  <th className="py-3 px-4 text-right">Subtotal</th>
                  <th className="py-3 px-4 text-right">IVA (16%)</th>
                  <th className="py-3 px-4 text-right">Total</th>
                  <th className="py-3 px-4 text-center">Estado Fiscal</th>
                  <th className="py-3 px-4 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoadingTickets ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-slate-400">
                      Cargando historial de tickets...
                    </td>
                  </tr>
                ) : tickets.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-slate-400">
                      No se han emitido tickets en esta sesión de caja.
                    </td>
                  </tr>
                ) : (
                  tickets.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-bold text-slate-900">{t.folio}</td>
                      <td className="py-3 px-4 text-slate-500">
                        {new Date(t.created_at).toLocaleString('es-MX')}
                      </td>
                      <td className="py-3 px-4 text-slate-700 font-medium">{t.customer_name}</td>
                      <td className="py-3 px-4 font-semibold text-slate-700">{t.payment_method}</td>
                      <td className="py-3 px-4 text-right font-medium text-slate-600">${t.subtotal?.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right font-medium text-slate-600">${t.tax_iva_total?.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900">${t.total?.toFixed(2)}</td>
                      <td className="py-3 px-4 text-center">
                        {t.is_globally_invoiced ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-800">
                            FACTURADO GLOBAL
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                            PENDIENTE GLOBAL
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => setReceiptTicket(t)}
                          className="p-1 hover:bg-slate-100 rounded text-slate-600 hover:text-blue-600 transition"
                          title="Imprimir Ticket"
                        >
                          <Printer className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODALS */}
      {showOpenSessionModal && (
        <OpenSessionModal
          registers={registers}
          selectedRegisterId={selectedRegisterId}
          onSelectRegister={setSelectedRegisterId}
          onOpenSession={handleOpenSession}
          isLoading={isSubmitting}
        />
      )}

      <PaymentModal
        isOpen={showPaymentModal}
        total={cartTotal}
        onClose={() => setShowPaymentModal(false)}
        onConfirmPayment={handleConfirmPayment}
        isLoading={isSubmitting}
      />

      <CorteXModal
        data={corteXData}
        isOpen={showCorteXModal}
        onClose={() => setShowCorteXModal(false)}
      />

      <CorteZModal
        isOpen={showCorteZModal}
        onClose={() => setShowCorteZModal(false)}
        onConfirmCorteZ={handleConfirmCorteZ}
        isLoading={isSubmitting}
      />

      <CashMovementModal
        isOpen={showMovementModal}
        onClose={() => setShowMovementModal(false)}
        onConfirmMovement={handleCashMovement}
        isLoading={isSubmitting}
      />

      <TicketReceiptModal
        ticket={receiptTicket}
        isOpen={!!receiptTicket}
        onClose={() => setReceiptTicket(null)}
      />

      <GlobalInvoiceModal
        branchId={activeSession?.cash_register_id || ''}
        isOpen={showGlobalInvoiceModal}
        onClose={() => setShowGlobalInvoiceModal(false)}
        onSuccess={() => {
          showToast('Factura Global CFDI 4.0 timbrada exitosamente.');
          loadTickets();
        }}
      />
    </motion.div>
  );
};
export default POSView;

