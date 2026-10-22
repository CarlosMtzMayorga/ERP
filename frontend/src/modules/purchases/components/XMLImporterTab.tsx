import React, { useState, useRef } from 'react';
import { XMLInvoicePreview } from '../types';
import {
  UploadCloud,
  FileCheck2,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  Trash2,
  Building2,
  Layers,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { apiClient } from '../../../api/axiosClient';

interface Props {
  branches: any[];
  warehouses: any[];
  currencies: any[];
  onImportComplete: () => void;
}

export const XMLImporterTab: React.FC<Props> = ({
  branches,
  warehouses,
  currencies,
  onImportComplete,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [parsedInvoices, setParsedInvoices] = useState<XMLInvoicePreview[]>([]);
  const [branchId, setBranchId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [currencyId, setCurrencyId] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-select first branch, warehouse, currency if available
  React.useEffect(() => {
    if (branches.length > 0 && !branchId) setBranchId(branches[0].id);
    if (warehouses.length > 0 && !warehouseId) setWarehouseId(warehouses[0].id);
    if (currencies.length > 0 && !currencyId) setCurrencyId(currencies[0].id);
  }, [branches, warehouses, currencies]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFiles(Array.from(e.target.files));
    }
  };

  const processFiles = async (files: File[]) => {
    const xmlFiles = files.filter(
      (f) => f.name.toLowerCase().endsWith('.xml') || f.type === 'text/xml' || f.type === 'application/xml'
    );

    if (xmlFiles.length === 0) {
      alert('Por favor seleccione únicamente archivos con extensión .xml (CFDI 4.0).');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    xmlFiles.forEach((file) => {
      formData.append('files', file);
    });

    try {
      const response = await apiClient.post<XMLInvoicePreview[]>('/purchases/xml/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      // Append or replace
      setParsedInvoices((prev) => [...prev, ...response.data]);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al procesar los archivos XML.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveInvoice = (uuid: string) => {
    setParsedInvoices(parsedInvoices.filter((inv) => inv.uuid !== uuid));
  };

  const handleConfirmImport = async () => {
    if (parsedInvoices.length === 0) {
      alert('No hay facturas XML pendientes de importar.');
      return;
    }
    if (!branchId || !warehouseId || !currencyId) {
      alert('Por favor configure la sucursal, almacén y moneda de destino para la importación.');
      return;
    }

    setImporting(true);
    try {
      await apiClient.post('/purchases/xml/confirm', {
        branch_id: branchId,
        warehouse_id: warehouseId,
        currency_id: currencyId,
        invoices: parsedInvoices,
      });

      alert(`¡Se importaron con éxito ${parsedInvoices.length} facturas y sus pasivos en CxP!`);
      setParsedInvoices([]);
      onImportComplete();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al confirmar la importación de facturas.');
    } finally {
      setImporting(false);
    }
  };

  const totalSum = parsedInvoices.reduce((acc, inv) => acc + Number(inv.total), 0);

  return (
    <div className="space-y-6">
      {/* Target Configuration Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1">Sucursal Destino *</label>
          <select
            value={branchId}
            onChange={(e) => setBranchId(e.target.value)}
            className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
          >
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1">Almacén Destino *</label>
          <select
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
            className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
          >
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1">Moneda *</label>
          <select
            value={currencyId}
            onChange={(e) => setCurrencyId(e.target.value)}
            className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-blue-500/20"
          >
            {currencies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} - {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Drag & Drop Dropzone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-3xl p-8 sm:p-12 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-blue-500 bg-blue-50/70 scale-[1.01]'
            : 'border-slate-300 bg-white hover:bg-slate-50/60'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".xml"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm shadow-blue-500/20">
          <UploadCloud className="w-8 h-8" />
        </div>

        <h3 className="text-base font-extrabold text-slate-900">
          {uploading ? 'Parseando archivos XML...' : 'Arrastra aquí tus archivos XML (CFDI 4.0)'}
        </h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
          Sube facturas de proveedores (.xml). El sistema extraerá automáticamente el RFC, conceptos, impuestos y generará los pasivos en CxP.
        </p>

        <button
          type="button"
          disabled={uploading}
          className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors"
        >
          {uploading ? 'Procesando...' : 'O explorar archivos en este equipo'}
        </button>
      </div>

      {/* Invoices Preview Table */}
      {parsedInvoices.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden space-y-4 p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h4 className="text-sm font-bold text-slate-900 flex items-center">
                <FileCheck2 className="w-4 h-4 mr-2 text-blue-600" />
                Pre-visualización de Facturas Detectadas ({parsedInvoices.length})
              </h4>
              <p className="text-xs text-slate-500">Revise los importes y datos fiscales antes de confirmar.</p>
            </div>

            <div className="flex items-center space-x-4">
              <div className="text-right">
                <span className="text-[11px] text-slate-400 font-medium">Total a Generar en CxP:</span>
                <p className="text-base font-extrabold text-blue-600">
                  ${totalSum.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>

              <button
                onClick={handleConfirmImport}
                disabled={importing}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-md shadow-blue-500/20 flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>{importing ? 'Importando...' : 'Confirmar Importación a CxP'}</span>
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Proveedor / Emisor</th>
                  <th className="py-2.5 px-3">Folio / UUID SAT</th>
                  <th className="py-2.5 px-3">Fecha</th>
                  <th className="py-2.5 px-3 text-center">Conceptos</th>
                  <th className="py-2.5 px-3 text-right">Subtotal</th>
                  <th className="py-2.5 px-3 text-right">IVA (16%)</th>
                  <th className="py-2.5 px-3 text-right">Total</th>
                  <th className="py-2.5 px-3 text-center">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {parsedInvoices.map((inv) => (
                  <tr key={inv.uuid} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-3">
                      <div className="flex items-center space-x-1.5">
                        {inv.supplier_exists ? (
                          <span className="w-2 h-2 rounded-full bg-emerald-500" title="Proveedor registrado" />
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-amber-500" title="Se dará de alta automáticamente" />
                        )}
                        <span className="font-bold text-slate-900 max-w-[200px] truncate">
                          {inv.emisor_nombre}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 ml-3.5">RFC: {inv.emisor_rfc}</span>
                    </td>

                    <td className="py-3 px-3">
                      <p className="font-bold text-slate-800">
                        {inv.serie ? `${inv.serie}-` : ''}{inv.folio || 'S/F'}
                      </p>
                      <p className="text-[10px] text-slate-400 font-mono truncate max-w-[150px]">
                        {inv.uuid}
                      </p>
                    </td>

                    <td className="py-3 px-3 text-slate-500">
                      {new Date(inv.fecha).toLocaleDateString('es-MX')}
                    </td>

                    <td className="py-3 px-3 text-center font-bold text-slate-600">
                      {inv.concepts.length}
                    </td>

                    <td className="py-3 px-3 text-right text-slate-700">
                      ${Number(inv.subtotal).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>

                    <td className="py-3 px-3 text-right text-slate-700">
                      ${Number(inv.total_iva).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>

                    <td className="py-3 px-3 text-right font-extrabold text-slate-900">
                      ${Number(inv.total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>

                    <td className="py-3 px-3 text-center">
                      <button
                        onClick={() => handleRemoveInvoice(inv.uuid)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-100"
                        title="Descartar factura"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

