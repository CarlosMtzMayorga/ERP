import React, { useState, useEffect } from 'react';
import {
  Banknote,
  CreditCard,
  Layers,
  ArrowRight,
  X,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

interface PaymentModalProps {
  total: number;
  isOpen: boolean;
  onClose: () => void;
  onConfirmPayment: (paymentData: {
    payment_method: string;
    amount_paid: number;
    amount_cash?: number;
    amount_card?: number;
    amount_transfer?: number;
  }) => Promise<void>;
  isLoading: boolean;
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  total,
  isOpen,
  onClose,
  onConfirmPayment,
  isLoading,
}) => {
  const [method, setMethod] = useState<'EFECTIVO' | 'TARJETA' | 'MIXTO'>('EFECTIVO');
  const [cashAmount, setCashAmount] = useState<string>(total.toFixed(2));
  const [cardAmount, setCardAmount] = useState<string>('0.00');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setMethod('EFECTIVO');
      setCashAmount(total.toFixed(2));
      setCardAmount('0.00');
      setError(null);
    }
  }, [isOpen, total]);

  if (!isOpen) return null;

  const cashVal = parseFloat(cashAmount) || 0;
  const cardVal = parseFloat(cardAmount) || 0;

  // Calculo de cambio
  let totalReceived = 0;
  let change = 0;
  let remaining = 0;

  if (method === 'EFECTIVO') {
    totalReceived = cashVal;
    change = Math.max(0, cashVal - total);
    remaining = Math.max(0, total - cashVal);
  } else if (method === 'TARJETA') {
    totalReceived = total;
    change = 0;
    remaining = 0;
  } else if (method === 'MIXTO') {
    totalReceived = cashVal + cardVal;
    change = Math.max(0, totalReceived - total);
    remaining = Math.max(0, total - totalReceived);
  }

  const handlePreset = (preset: number) => {
    setCashAmount(preset.toFixed(2));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (method === 'EFECTIVO' && cashVal < total) {
      setError(`El monto recibido en efectivo ($${cashVal.toFixed(2)}) es menor al total del ticket ($${total.toFixed(2)}).`);
      return;
    }

    if (method === 'MIXTO' && totalReceived < total) {
      setError(`La suma de efectivo y tarjeta ($${totalReceived.toFixed(2)}) es menor al total ($${total.toFixed(2)}).`);
      return;
    }

    try {
      await onConfirmPayment({
        payment_method: method,
        amount_paid: method === 'EFECTIVO' ? cashVal : totalReceived,
        amount_cash: method === 'EFECTIVO' ? cashVal : (method === 'MIXTO' ? cashVal : 0),
        amount_card: method === 'TARJETA' ? total : (method === 'MIXTO' ? cardVal : 0),
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al procesar el cobro del ticket.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-slate-900 p-5 text-white flex items-center justify-between">
          <div>
            <span className="text-xs uppercase tracking-wider text-blue-400 font-semibold">Módulo de Cobro Rápido</span>
            <h3 className="text-xl font-bold">Liquidación de Ticket</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Total Banner */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 p-6 text-white text-center">
          <span className="text-xs uppercase tracking-widest text-blue-200 font-medium">Total a Pagar</span>
          <div className="text-4xl font-extrabold tracking-tight mt-1">
            ${total.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MXN
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-start space-x-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Payment Method Selector */}
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => {
                setMethod('EFECTIVO');
                setCashAmount(total.toFixed(2));
              }}
              className={`p-3 rounded-xl border flex flex-col items-center justify-center space-y-1.5 transition ${
                method === 'EFECTIVO'
                  ? 'border-blue-600 bg-blue-50/70 text-blue-700 shadow-sm'
                  : 'border-slate-200 hover:bg-slate-50 text-slate-600'
              }`}
            >
              <Banknote className="w-5 h-5" />
              <span className="text-xs font-bold">Efectivo</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMethod('TARJETA');
                setCardAmount(total.toFixed(2));
              }}
              className={`p-3 rounded-xl border flex flex-col items-center justify-center space-y-1.5 transition ${
                method === 'TARJETA'
                  ? 'border-blue-600 bg-blue-50/70 text-blue-700 shadow-sm'
                  : 'border-slate-200 hover:bg-slate-50 text-slate-600'
              }`}
            >
              <CreditCard className="w-5 h-5" />
              <span className="text-xs font-bold">Tarjeta</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMethod('MIXTO');
                setCashAmount((total / 2).toFixed(2));
                setCardAmount((total / 2).toFixed(2));
              }}
              className={`p-3 rounded-xl border flex flex-col items-center justify-center space-y-1.5 transition ${
                method === 'MIXTO'
                  ? 'border-blue-600 bg-blue-50/70 text-blue-700 shadow-sm'
                  : 'border-slate-200 hover:bg-slate-50 text-slate-600'
              }`}
            >
              <Layers className="w-5 h-5" />
              <span className="text-xs font-bold">Mixto</span>
            </button>
          </div>

          {/* Efectivo Inputs & Presets */}
          {(method === 'EFECTIVO' || method === 'MIXTO') && (
            <div className="space-y-3">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                {method === 'MIXTO' ? 'Monto en Efectivo' : 'Efectivo Recibido'}
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 font-bold text-lg">
                  $
                </span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={cashAmount}
                  onChange={(e) => setCashAmount(e.target.value)}
                  className="w-full text-2xl font-bold pl-8 pr-4 py-2.5 rounded-xl border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 text-right"
                  placeholder="0.00"
                  autoFocus
                />
              </div>

              {method === 'EFECTIVO' && (
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handlePreset(total)}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-lg transition"
                  >
                    Exacto (${total.toFixed(2)})
                  </button>
                  {[50, 100, 200, 500, 1000]
                    .filter((p) => p >= total || p === 50)
                    .map((preset) => (
                      <button
                        type="button"
                        key={preset}
                        onClick={() => handlePreset(preset)}
                        className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold rounded-lg transition border border-blue-200"
                      >
                        ${preset}.00
                      </button>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* Tarjeta Input for Mixto */}
          {method === 'MIXTO' && (
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Monto en Tarjeta / Terminal Bancaria
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 font-bold text-lg">
                  $
                </span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={cardAmount}
                  onChange={(e) => setCardAmount(e.target.value)}
                  className="w-full text-2xl font-bold pl-8 pr-4 py-2.5 rounded-xl border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 text-right"
                  placeholder="0.00"
                />
              </div>
            </div>
          )}

          {/* Live Change / Restante Display */}
          <div className="rounded-2xl p-4 bg-slate-50 border border-slate-200 flex items-center justify-between">
            {remaining > 0 ? (
              <>
                <div>
                  <span className="text-xs font-bold text-amber-700 uppercase tracking-wide block">Resta por Pagar</span>
                  <span className="text-xs text-slate-500">Monto incompleto</span>
                </div>
                <div className="text-2xl font-black text-amber-600">
                  ${remaining.toFixed(2)}
                </div>
              </>
            ) : (
              <>
                <div>
                  <span className="text-xs font-bold text-emerald-700 uppercase tracking-wide block">Cambio a Regresar</span>
                  <span className="text-xs text-slate-500">Entregar al cliente</span>
                </div>
                <div className="text-3xl font-black text-emerald-600">
                  ${change.toFixed(2)}
                </div>
              </>
            )}
          </div>

          {/* Submit Action */}
          <button
            type="submit"
            disabled={isLoading || (remaining > 0 && method !== 'TARJETA')}
            className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl font-bold shadow-lg shadow-emerald-600/25 flex items-center justify-center space-x-2 transition text-base"
          >
            {isLoading ? (
              <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                <CheckCircle2 className="w-5 h-5" />
                <span>Confirmar Pago e Imprimir Ticket</span>
                <ArrowRight className="w-4 h-4 ml-1" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
