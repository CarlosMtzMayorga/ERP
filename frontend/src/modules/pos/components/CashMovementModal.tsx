import React, { useState } from 'react';
import { ArrowDownRight, ArrowUpRight, X, CheckCircle2, DollarSign } from 'lucide-react';

interface CashMovementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmMovement: (type: 'ENTRY' | 'WITHDRAWAL', amount: number, reason: string) => Promise<void>;
  isLoading: boolean;
}

export const CashMovementModal: React.FC<CashMovementModalProps> = ({
  isOpen,
  onClose,
  onConfirmMovement,
  isLoading,
}) => {
  const [type, setType] = useState<'ENTRY' | 'WITHDRAWAL'>('ENTRY');
  const [amount, setAmount] = useState<string>('');
  const [reason, setReason] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const num = parseFloat(amount);
    if (isNaN(num) || num <= 0) {
      setError('Ingrese un monto válido mayor a $0.00.');
      return;
    }
    if (!reason.trim()) {
      setError('El motivo o justificación del movimiento es obligatorio.');
      return;
    }

    try {
      await onConfirmMovement(type, num, reason.trim());
      setAmount('');
      setReason('');
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al registrar el movimiento de efectivo.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-slate-900 p-5 text-white flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold">Movimiento de Efectivo en Caja</h3>
            <p className="text-xs text-slate-400">Entrada de cambio o retiro parcial de seguridad</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-rose-700 text-xs">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setType('ENTRY')}
              className={`p-3 rounded-xl border flex flex-col items-center justify-center space-y-1 transition ${
                type === 'ENTRY'
                  ? 'border-emerald-600 bg-emerald-50 text-emerald-700 font-bold'
                  : 'border-slate-200 hover:bg-slate-50 text-slate-600'
              }`}
            >
              <ArrowUpRight className="w-5 h-5 text-emerald-600" />
              <span className="text-xs">Entrada (Cambio)</span>
            </button>
            <button
              type="button"
              onClick={() => setType('WITHDRAWAL')}
              className={`p-3 rounded-xl border flex flex-col items-center justify-center space-y-1 transition ${
                type === 'WITHDRAWAL'
                  ? 'border-rose-600 bg-rose-50 text-rose-700 font-bold'
                  : 'border-slate-200 hover:bg-slate-50 text-slate-600'
              }`}
            >
              <ArrowDownRight className="w-5 h-5 text-rose-600" />
              <span className="text-xs">Retiro de Seguridad</span>
            </button>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Monto en Efectivo
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 font-bold">$</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full text-xl font-bold pl-8 pr-3 py-2 rounded-xl border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
                required
                autoFocus
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Motivo / Justificación
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={type === 'ENTRY' ? 'Ej. Dotación adicional de monedas' : 'Ej. Traspaso a caja fuerte por límite de $5,000'}
              className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg text-slate-800 focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 px-3 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-xs transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 py-2.5 px-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-xl font-bold text-xs transition shadow-lg shadow-blue-500/25 flex items-center justify-center space-x-1"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Registrar</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
