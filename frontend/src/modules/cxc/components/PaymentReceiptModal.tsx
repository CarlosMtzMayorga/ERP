import React from 'react';
import { ShieldCheck, X, Printer, CheckCircle2 } from 'lucide-react';

interface PaymentReceiptModalProps {
  receipt: any | null;
  isOpen: boolean;
  onClose: () => void;
}

export const PaymentReceiptModal: React.FC<PaymentReceiptModalProps> = ({
  receipt,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !receipt) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-emerald-800 p-6 text-white text-center">
          <div className="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-3 backdrop-blur-md border border-white/20">
            <ShieldCheck className="w-8 h-8 text-emerald-200" />
          </div>
          <h3 className="text-xl font-bold">¡Pago Aplicado y Timbrado!</h3>
          <p className="text-xs text-emerald-200 mt-1">
            Complemento de Recepción de Pagos (REP 2.0 / CFDI 4.0)
          </p>
        </div>

        <div className="p-6 space-y-4 text-xs">
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2.5">
            <div className="flex justify-between">
              <span className="text-slate-500 font-semibold">Folio Recibo:</span>
              <span className="font-bold text-slate-800">{receipt.folio}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500 font-semibold">UUID Fiscal SAT:</span>
              <span className="font-mono font-bold text-indigo-700 truncate max-w-[200px]">
                {receipt.uuid}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500 font-semibold">Monto Pagado:</span>
              <span className="font-black text-emerald-700 text-sm">
                ${Number(receipt.amount).toFixed(2)} MXN
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500 font-semibold">Facturas Relacionadas:</span>
              <span className="font-bold text-slate-800">
                {receipt.related_documents_count || 1} factura(s)
              </span>
            </div>
          </div>

          <div className="pt-2 flex gap-3">
            <button
              onClick={() => window.print()}
              className="flex-1 py-2.5 px-3 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold flex items-center justify-center space-x-1.5 transition"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimir</span>
            </button>
            <button
              onClick={onClose}
              className="flex-1 py-2.5 px-3 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold transition"
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

