import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  FileText,
  Plus,
  Zap,
  CheckCircle2,
  AlertCircle,
  Building2,
  RefreshCw,
  Hash,
  Layers,
} from 'lucide-react';

interface FolioSeriesItem {
  id: string;
  branch_id?: string;
  branch_name?: string;
  document_type: string;
  serie: string;
  current_folio: number;
  initial_folio: number;
  final_folio?: number;
  is_default: boolean;
}

interface BranchItem {
  id: string;
  code: string;
  name: string;
}

export const FoliosTab: React.FC = () => {
  const [series, setSeries] = useState<FolioSeriesItem[]>([]);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [testingSerie, setTestingSerie] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  // Form state
  const [docType, setDocType] = useState('FAC');
  const [serieCode, setSerieCode] = useState('A');
  const [branchId, setBranchId] = useState<string>('');
  const [initialFolio, setInitialFolio] = useState<number>(1);
  const [finalFolio, setFinalFolio] = useState<string>('');
  const [isDefault, setIsDefault] = useState(true);

  const fetchFolios = async () => {
    setLoading(true);
    try {
      const [seriesRes, branchesRes] = await Promise.all([
        apiClient.get<FolioSeriesItem[]>('/config/folios'),
        apiClient.get<BranchItem[]>('/tenants/branches'),
      ]);
      setSeries(seriesRes.data);
      setBranches(branchesRes.data);
    } catch (err) {
      console.error('Error fetching folios:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFolios();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.post('/config/folios', {
        document_type: docType,
        serie: serieCode,
        branch_id: branchId || null,
        initial_folio: initialFolio,
        final_folio: finalFolio ? parseInt(finalFolio) : null,
        is_default: isDefault,
      });
      setIsModalOpen(false);
      setSerieCode('');
      fetchFolios();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al crear serie de folios.');
    }
  };

  const handleConsumeTest = async (serieItem: FolioSeriesItem) => {
    setTestingSerie(serieItem.id);
    setTestResult(null);
    try {
      const res = await apiClient.post<{ formatted_folio: string; folio: number }>('/config/folios/consume', {
        document_type: serieItem.document_type,
        branch_id: serieItem.branch_id || null,
        serie: serieItem.serie,
      });
      setTestResult(
        `¡Folio consumido con éxito mediante SELECT FOR UPDATE! Asignado: ${res.data.formatted_folio}`
      );
      fetchFolios();
    } catch (err: any) {
      setTestResult(`Error en consumo: ${err.response?.data?.detail || err.message}`);
    } finally {
      setTestingSerie(null);
    }
  };

  const docTypeLabels: Record<string, string> = {
    FAC: 'Factura Electrónica (CFDI)',
    COT: 'Cotización',
    PED: 'Pedido de Venta',
    REM: 'Remisión de Almacén',
    TICK: 'Ticket de Punto de Venta (POS)',
    REP: 'Complemento de Pago (REP 2.0)',
    NOM: 'Recibo de Nómina (CFDI 1.2)',
    TRASP: 'Traspaso entre Almacenes',
    AJUST: 'Ajuste de Inventario',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-soft">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-600" />
            <span>Control de Series y Folios Transaccionales</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Garantía de concurrencia atómica con bloqueo a nivel de fila (PostgreSQL SELECT FOR UPDATE).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchFolios}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
            title="Refrescar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Nueva Serie</span>
          </button>
        </div>
      </div>

      {testResult && (
        <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span className="font-mono">{testResult}</span>
          </div>
          <button onClick={() => setTestResult(null)} className="text-blue-500 hover:text-blue-800 font-bold ml-4">
            ✕
          </button>
        </div>
      )}

      {/* Series Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-6 py-4">Tipo de Documento</th>
                <th className="px-6 py-4">Serie</th>
                <th className="px-6 py-4">Folio Actual</th>
                <th className="px-6 py-4">Rango (Inicial - Final)</th>
                <th className="px-6 py-4">Sucursal</th>
                <th className="px-6 py-4 text-center">Predeterminada</th>
                <th className="px-6 py-4 text-right">Prueba Atómica</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-slate-400">
                    Cargando series de folios...
                  </td>
                </tr>
              ) : series.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-slate-400">
                    No hay series configuradas para esta empresa.
                  </td>
                </tr>
              ) : (
                series.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-bold text-slate-900">{item.document_type}</div>
                      <div className="text-[11px] text-slate-500">{docTypeLabels[item.document_type] || item.document_type}</div>
                    </td>
                    <td className="px-6 py-4 font-mono font-bold text-blue-600 text-sm">
                      {item.serie}
                    </td>
                    <td className="px-6 py-4 font-mono text-slate-900 font-semibold">
                      <span className="px-2 py-1 bg-slate-100 rounded-lg">
                        #{item.current_folio}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-slate-600">
                      {item.initial_folio} - {item.final_folio ? item.final_folio : 'Ilimitado'}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1 text-slate-700">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        <span>{item.branch_name || 'Todas'}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {item.is_default ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          SÍ
                        </span>
                      ) : (
                        <span className="text-slate-400 text-xs">No</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleConsumeTest(item)}
                        disabled={testingSerie === item.id}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-[11px] font-semibold transition-colors disabled:opacity-50"
                        title="Ejecutar bloqueo SELECT FOR UPDATE y consumir 1 folio de prueba"
                      >
                        <Zap className="w-3.5 h-3.5 text-blue-600" />
                        <span>{testingSerie === item.id ? 'Bloqueando...' : 'Test Folio +1'}</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Nueva Serie */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-8 shadow-card border border-slate-100 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Nueva Serie Transaccional</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <form onSubmit={handleCreate} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Tipo de Documento
                </label>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-blue-500/20"
                >
                  {Object.entries(docTypeLabels).map(([code, label]) => (
                    <option key={code} value={code}>
                      {code} - {label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Código de Serie (ej. A, B, POS, MATRIZ)
                </label>
                <input
                  type="text"
                  required
                  maxLength={10}
                  value={serieCode}
                  onChange={(e) => setSerieCode(e.target.value.toUpperCase())}
                  placeholder="FAC"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs uppercase font-mono font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Sucursal Asignada
                </label>
                <select
                  value={branchId}
                  onChange={(e) => setBranchId(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                >
                  <option value="">Todas las sucursales (Global)</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.code} - {b.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Folio Inicial
                  </label>
                  <input
                    type="number"
                    min={1}
                    required
                    value={initialFolio}
                    onChange={(e) => setInitialFolio(parseInt(e.target.value))}
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Folio Límite (Opcional)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={finalFolio}
                    onChange={(e) => setFinalFolio(e.target.value)}
                    placeholder="Sin límite"
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="defaultSerie"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="defaultSerie" className="text-xs text-slate-700 font-medium">
                  Marcar como serie predeterminada para este documento
                </label>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20"
                >
                  Guardar Serie
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
