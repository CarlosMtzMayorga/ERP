import React, { useState } from 'react';
import { CashRegister } from '../types';
import { DollarSign, ShieldAlert, KeyRound, CheckCircle2 } from 'lucide-react';

interface OpenSessionModalProps {
  registers: CashRegister[];
  selectedRegisterId: string;
  onSelectRegister: (id: string) => void;
  onOpenSession: (registerId: string, initialCash: number, notes?: string) => Promise<void>;
  isLoading: boolean;
}

export const OpenSessionModal: React.FC<OpenSessionModalProps> = ({
  registers,
  selectedRegisterId,
  onSelectRegister,
  onOpenSession,
  isLoading,
}) => {
  const [initialCash, setInitialCash] = useState<string>('500.00');
  const [notes, setNotes] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const amount = parseFloat(initialCash);
    if (isNaN(amount) || amount < 0) {
      setError('Por favor ingrese un fondo de apertura válido (igual o mayor a $0.00).');
      return;
    }
    if (!selectedRegisterId) {
      setError('Debe seleccionar una caja registradora para operar.');
      return;
    }

    try {
      await onOpenSession(selectedRegisterId, amount, notes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al abrir el turno de caja.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-gradient-to-r from-blue-700 to-indigo-800 p-6 text-white text-center relative">
          <div className="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-3 backdrop-blur-md border border-white/20">
            <KeyRound className="w-7 h-7 text-blue-200" />
          </div>
          <h2 className="text-xl font-bold tracking-tight">Apertura de Turno de Caja</h2>
          <p className="text-xs text-blue-200 mt-1">
            Control de Efectivo y Trazabilidad SAT Microsip
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-start space-x-3 text-amber-800 text-xs">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <span>
              <strong>Regla de Control:</strong> No se pueden emitir tickets sin declarar previamente un fondo inicial de apertura.
            </span>
          </div>

          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-rose-700 text-xs">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Terminal / Caja Registradora
            </label>
            <select
              value={selectedRegisterId}
              onChange={(e) => onSelectRegister(e.target.value)}
              className="w-full text-sm rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium"
              required
            >
              {registers.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.code} - {r.name} ({r.branch_name || 'Sucursal Principal'})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Fondo Inicial de Caja (Efectivo)
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <DollarSign className="w-4 h-4" />
              </div>
              <input
                type="number"
                step="0.01"
                min="0"
                value={initialCash}
                onChange={(e) => setInitialCash(e.target.value)}
                className="w-full text-lg font-bold pl-9 pr-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
                required
                autoFocus
              />
            </div>
            <div className="flex gap-2 mt-2">
              {['200.00', '500.00', '1000.00', '1500.00'].map((preset) => (
                <button
                  type="button"
                  key={preset}
                  onClick={() => setInitialCash(preset)}
                  className="px-2.5 py-1 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md transition"
                >
                  ${preset}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Notas u Observaciones (Opcional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full text-sm px-3 py-2 rounded-lg border border-slate-300 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ej. Fondo entregado en monedas y billetes chicos"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-xl font-bold shadow-lg shadow-blue-500/25 flex items-center justify-center space-x-2 transition text-sm"
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Iniciar Turno de Caja</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
