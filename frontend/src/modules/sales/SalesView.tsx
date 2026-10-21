import React, { useState } from 'react';
import {
  ShoppingCart,
  FileCheck2,
  PlusCircle,
  Layers,
  ArrowRightLeft,
} from 'lucide-react';
import { SalesDocumentsTab } from './components/SalesDocumentsTab';
import { SalesCaptureTab } from './components/SalesCaptureTab';

export const SalesView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'documents' | 'capture'>('documents');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <ShoppingCart className="w-6 h-6 text-blue-600" />
            <span>Módulo 3: Ventas y Facturación Electrónica</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Flujo documental Cotización $\rightarrow$ Pedido $\rightarrow$ Factura CFDI 4.0 con sellado CSD y reserva de inventario.
          </p>
        </div>

        {/* Tab switcher button */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab(activeTab === 'documents' ? 'capture' : 'documents')}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 transition-all cursor-pointer"
          >
            {activeTab === 'documents' ? (
              <>
                <PlusCircle className="w-4 h-4" />
                <span>Nueva Venta / Captura</span>
              </>
            ) : (
              <>
                <FileCheck2 className="w-4 h-4" />
                <span>Ver Gestor de Documentos</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Tab Rendering */}
      {activeTab === 'documents' ? (
        <SalesDocumentsTab onGoToCapture={() => setActiveTab('capture')} />
      ) : (
        <SalesCaptureTab onDocumentCreated={() => setActiveTab('documents')} />
      )}
    </div>
  );
};
