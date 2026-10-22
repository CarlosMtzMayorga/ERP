import React, { useState } from 'react';
import {
  ShoppingCart,
  FileCheck2,
  PlusCircle,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { SalesDocumentsTab } from './components/SalesDocumentsTab';
import { SalesCaptureTab } from './components/SalesCaptureTab';

export const SalesView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'documents' | 'capture'>('documents');

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="space-y-6 max-w-7xl mx-auto font-sans"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] flex items-center justify-center">
              <ShoppingCart className="w-5 h-5 text-[#047857]" />
            </div>
            <span>Módulo 3: Ventas y Facturación Electrónica</span>
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Flujo documental Cotización &rarr; Pedido &rarr; Factura CFDI 4.0 con sellado CSD y reserva de inventario.
          </p>
        </div>

        {/* Tab switcher button in Emerald (#047857) */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab(activeTab === 'documents' ? 'capture' : 'documents')}
            className="flex items-center gap-2 px-4 py-2.5 bg-[#047857] hover:bg-emerald-800 text-white rounded-xl text-xs font-semibold shadow-sm shadow-emerald-950/20 active:scale-95 transition-all cursor-pointer"
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
    </motion.div>
  );
};
