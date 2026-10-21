import React from 'react';
import { POSTicket } from '../types';
import { Printer, CheckCircle, X } from 'lucide-react';

interface TicketReceiptModalProps {
  ticket: POSTicket | null;
  isOpen: boolean;
  onClose: () => void;
}

export const TicketReceiptModal: React.FC<TicketReceiptModalProps> = ({ ticket, isOpen, onClose }) => {
  if (!isOpen || !ticket) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
        {/* Modal Top Bar */}
        <div className="bg-slate-900 px-4 py-3 text-white flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-bold uppercase tracking-wider">Ticket Emitido</span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Thermal Receipt Paper Layout */}
        <div className="p-6 bg-slate-50 overflow-y-auto flex-1 font-mono text-xs text-slate-800 leading-relaxed border-b">
          <div className="text-center pb-3 border-b border-dashed border-slate-300">
            <h4 className="font-bold text-sm text-slate-900 uppercase">ERP SAAS FINANCIAL</h4>
            <p className="text-[11px] text-slate-500">RFC: EMP200101XYZ</p>
            <p className="text-[11px] text-slate-500">Sucursal Matriz - CP 06000</p>
            <p className="text-[10px] text-slate-400 mt-1">Régimen Fiscal: 601 General de Ley</p>
          </div>

          <div className="py-2.5 border-b border-dashed border-slate-300 space-y-1 text-[11px]">
            <div className="flex justify-between">
              <span>FOLIO:</span>
              <span className="font-bold">{ticket.folio}</span>
            </div>
            <div className="flex justify-between">
              <span>FECHA:</span>
              <span>{new Date(ticket.created_at || Date.now()).toLocaleString('es-MX')}</span>
            </div>
            <div className="flex justify-between">
              <span>CAJA:</span>
              <span>{ticket.cash_register_name || 'Caja 01'}</span>
            </div>
            <div className="flex justify-between">
              <span>CLIENTE:</span>
              <span>{ticket.customer_name || 'PUBLICO EN GENERAL'}</span>
            </div>
          </div>

          {/* Items */}
          <div className="py-3 border-b border-dashed border-slate-300">
            <div className="flex justify-between font-bold text-[10px] uppercase text-slate-500 mb-1">
              <span>Cant. / Descrip.</span>
              <span>Importe</span>
            </div>
            {ticket.items && ticket.items.length > 0 ? (
              <div className="space-y-1.5">
                {ticket.items.map((it) => (
                  <div key={it.id}>
                    <div className="flex justify-between font-medium">
                      <span>{it.quantity} x {it.description}</span>
                      <span>${it.total.toFixed(2)}</span>
                    </div>
                    <div className="text-[10px] text-slate-400">
                      SKU: {it.sku} (IVA Inc.)
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-2 text-slate-400 italic">Venta en mostrador</div>
            )}
          </div>

          {/* Totals */}
          <div className="py-2.5 border-b border-dashed border-slate-300 space-y-1">
            <div className="flex justify-between text-[11px]">
              <span>Subtotal:</span>
              <span>${ticket.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span>IVA (16%):</span>
              <span>${ticket.tax_iva_total.toFixed(2)}</span>
            </div>
            <div className="flex justify-between font-bold text-sm text-slate-900 pt-1">
              <span>TOTAL:</span>
              <span>${ticket.total.toFixed(2)}</span>
            </div>
          </div>

          {/* Payment & Change */}
          <div className="py-2.5 border-b border-dashed border-slate-300 space-y-1 text-[11px]">
            <div className="flex justify-between">
              <span>FORMA DE PAGO:</span>
              <span className="font-bold">{ticket.payment_method}</span>
            </div>
            <div className="flex justify-between">
              <span>PAGO CON:</span>
              <span>${ticket.amount_paid.toFixed(2)}</span>
            </div>
            <div className="flex justify-between font-bold text-emerald-700">
              <span>CAMBIO:</span>
              <span>${ticket.change_returned.toFixed(2)}</span>
            </div>
          </div>

          {/* Barcode & Footer */}
          <div className="text-center pt-4 pb-2 space-y-2">
            <div className="h-8 bg-slate-800 text-white flex items-center justify-center tracking-widest text-[10px] font-mono rounded">
              *|| {ticket.folio} ||*
            </div>
            <p className="text-[9px] text-slate-400 leading-tight">
              Este comprobante forma parte de la Factura Global CFDI 4.0 al público en general.
            </p>
            <p className="text-[10px] font-bold text-slate-700">¡Gracias por su compra!</p>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="p-3 bg-white flex gap-2">
          <button
            onClick={() => window.print()}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-xs flex items-center justify-center space-x-1 transition shadow"
          >
            <Printer className="w-4 h-4" />
            <span>Imprimir</span>
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold text-xs transition"
          >
            Siguiente Venta (ESC)
          </button>
        </div>
      </div>
    </div>
  );
};
