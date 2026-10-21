import React, { useState } from 'react';
import {
  Lock,
  X,
  AlertTriangle,
  Calculator,
  CheckCircle2,
  DollarSign,
  CreditCard,
  Coins
} from 'lucide-react';

interface CorteZModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmCorteZ: (declaredCash: number, declaredCard: number, notes?: string) => Promise<any>;
  isLoading: boolean;
}

export const CorteZModal: React.FC<CorteZModalProps> = ({
  isOpen,
  onClose,
  onConfirmCorteZ,
  isLoading,
}) => {
  const [useCounter, setUseCounter] = useState<boolean>(true);
  const [denominations, setDenominations] = useState<{ [key: string]: number }>({
    b1000: 0,
    b500: 0,
    b200: 0,
    b100: 0,
    b50: 0,
    b20: 0,
    m10: 0,
    m5: 0,
    m2: 0,
    m1: 0,
    m05: 0,
  });

  const [directCash, setDirectCash] = useState<string>('');
  const [declaredCard, setDeclaredCard] = useState<string>('0.00');
  const [notes, setNotes] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  // Calculo total conteo de billetes y monedas
  const countedCash =
    (denominations.b1000 || 0) * 1000 +
    (denominations.b500 || 0) * 500 +
    (denominations.b200 || 0) * 200 +
    (denominations.b100 || 0) * 100 +
    (denominations.b50 || 0) * 50 +
    (denominations.b20 || 0) * 20 +
    (denominations.m10 || 0) * 10 +
    (denominations.m5 || 0) * 5 +
    (denominations.m2 || 0) * 2 +
    (denominations.m1 || 0) * 1 +
    (denominations.m05 || 0) * 0.5;

  const totalCashToSubmit = useCounter ? countedCash : parseFloat(directCash) || 0;
  const cardToSubmit = parseFloat(declaredCard) || 0;

  const handleDenomChange = (key: string, val: string) => {
    const num = parseInt(val) || 0;
    setDenominations((prev) => ({ ...prev, [key]: Math.max(0, num) }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (totalCashToSubmit < 0 || cardToSubmit < 0) {
      setError('Los montos declarados no pueden ser negativos.');
      return;
    }

    try {
      await onConfirmCorteZ(totalCashToSubmit, cardToSubmit, notes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al procesar el Corte Z.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden border border-slate-200 my-8 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-rose-900 p-5 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-rose-600 rounded-lg">
              <Lock className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-bold">Corte Z (Cierre Definitivo de Turno)</h3>
              <p className="text-xs text-rose-200">Arqueo a ciegas: Ingrese el dinero físico real</p>
            </div>
          </div>
          <button onClick={onClose} className="text-rose-300 hover:text-white p-1 rounded-lg hover:bg-rose-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-start space-x-2.5 text-amber-800 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong>Auditoría Ciega:</strong> Este proceso registrará irrevocablemente en la base de datos cualquier
              diferencia (<strong>Sobrante</strong> o <strong>Faltante</strong>) y cerrará la sesión de la caja.
            </div>
          </div>

          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-rose-700 text-xs">
              {error}
            </div>
          )}

          {/* Toggle Counter vs Direct Input */}
          <div className="flex justify-between items-center border-b pb-3">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Conteo de Efectivo Físico</span>
            <button
              type="button"
              onClick={() => setUseCounter(!useCounter)}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center space-x-1"
            >
              <Calculator className="w-3.5 h-3.5" />
              <span>{useCounter ? 'Ingreso Directo de Importe' : 'Usar Desglose por Denominación'}</span>
            </button>
          </div>

          {useCounter ? (
            <div className="space-y-4">
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-700 mb-2">
                  <DollarSign className="w-3.5 h-3.5 text-blue-600" />
                  <span>Billetes</span>
                </div>
                <div className="grid grid-cols-3 gap-2.5">
                  {[
                    { label: '$1,000', key: 'b1000' },
                    { label: '$500', key: 'b500' },
                    { label: '$200', key: 'b200' },
                    { label: '$100', key: 'b100' },
                    { label: '$50', key: 'b50' },
                    { label: '$20', key: 'b20' },
                  ].map((denom) => (
                    <div key={denom.key} className="flex items-center space-x-1.5 bg-white p-1.5 rounded-lg border border-slate-200">
                      <span className="text-xs font-bold text-slate-700 w-12">{denom.label}</span>
                      <input
                        type="number"
                        min="0"
                        value={denominations[denom.key] || ''}
                        onChange={(e) => handleDenomChange(denom.key, e.target.value)}
                        placeholder="0"
                        className="w-full text-right text-xs font-bold px-2 py-1 border border-slate-200 rounded focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-700 mb-2">
                  <Coins className="w-3.5 h-3.5 text-amber-600" />
                  <span>Monedas</span>
                </div>
                <div className="grid grid-cols-3 gap-2.5">
                  {[
                    { label: '$10', key: 'm10' },
                    { label: '$5', key: 'm5' },
                    { label: '$2', key: 'm2' },
                    { label: '$1', key: 'm1' },
                    { label: '$0.50', key: 'm05' },
                  ].map((denom) => (
                    <div key={denom.key} className="flex items-center space-x-1.5 bg-white p-1.5 rounded-lg border border-slate-200">
                      <span className="text-xs font-bold text-slate-700 w-12">{denom.label}</span>
                      <input
                        type="number"
                        min="0"
                        value={denominations[denom.key] || ''}
                        onChange={(e) => handleDenomChange(denom.key, e.target.value)}
                        placeholder="0"
                        className="w-full text-right text-xs font-bold px-2 py-1 border border-slate-200 rounded focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Efectivo Total Declarado
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 font-bold">$</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={directCash}
                  onChange={(e) => setDirectCash(e.target.value)}
                  className="w-full text-xl font-bold pl-8 pr-3 py-2 rounded-xl border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="0.00"
                  required
                />
              </div>
            </div>
          )}

          {/* Total Cash Declared Display */}
          <div className="bg-slate-900 rounded-xl p-3.5 text-white flex justify-between items-center">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Total Efectivo a Declarar:</span>
            <span className="text-2xl font-black text-emerald-400">
              ${totalCashToSubmit.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MXN
            </span>
          </div>

          {/* Tarjeta Vouchers */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
              <CreditCard className="w-3.5 h-3.5 text-indigo-600" />
              <span>Vouchers de Tarjeta / Terminales Bancarias Declaradas</span>
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400 font-bold">$</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={declaredCard}
                onChange={(e) => setDeclaredCard(e.target.value)}
                className="w-full text-lg font-bold pl-8 pr-3 py-2 rounded-xl border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
                required
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Notas u Observaciones del Cierre
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ej. Se encontraron 2 monedas falsas, redondeo en cambio"
              className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg text-slate-800 focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 px-4 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-xs transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 py-3 px-4 bg-rose-600 hover:bg-rose-700 disabled:bg-rose-300 text-white rounded-xl font-bold shadow-lg shadow-rose-600/25 flex items-center justify-center space-x-2 text-xs transition"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Cerrar Turno (Corte Z)</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
