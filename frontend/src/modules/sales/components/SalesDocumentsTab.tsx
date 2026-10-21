import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  FileText,
  TrendingUp,
  FileCheck2,
  Clock,
  DollarSign,
  Download,
  Zap,
  CheckCircle2,
  RefreshCw,
  Search,
  Filter,
  ArrowRight,
  Package,
} from 'lucide-react';

interface SalesDocItem {
  id: string;
  created_at: string;
  document_type: string;
  status: string;
  serie: string;
  folio: number;
  formatted_folio: string;
  customer_name: string;
  customer_rfc: string;
  subtotal: number;
  tax_iva_total: number;
  total: number;
  total_cost_cogs: number;
  cfdi_uuid?: string;
  cfdi_stamped_at?: string;
}

interface SalesMetrics {
  monthly_sales_total: number;
  stamped_invoices_count: number;
  pending_orders_count: number;
  average_ticket: number;
  top_products: Array<{
    sku: string;
    description: string;
    units_sold: number;
    revenue: number;
  }>;
}

interface SalesDocumentsTabProps {
  onGoToCapture: () => void;
}

export const SalesDocumentsTab: React.FC<SalesDocumentsTabProps> = ({ onGoToCapture }) => {
  const [documents, setDocuments] = useState<SalesDocItem[]>([]);
  const [metrics, setMetrics] = useState<SalesMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [docTypeFilter, setDocTypeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [alertMessage, setAlertMessage] = useState<string | null>(null);

  const fetchSalesData = async () => {
    setLoading(true);
    try {
      const [docsRes, metricsRes] = await Promise.all([
        apiClient.get<SalesDocItem[]>('/sales/documents'),
        apiClient.get<SalesMetrics>('/sales/dashboard'),
      ]);
      setDocuments(docsRes.data);
      setMetrics(metricsRes.data);
    } catch (err) {
      console.error('Error fetching sales data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSalesData();
  }, []);

  const handleConvertToInvoice = async (orderId: string) => {
    setActionLoading(orderId);
    setAlertMessage(null);
    try {
      const res = await apiClient.post<SalesDocItem>(`/sales/documents/${orderId}/convert-to-invoice`);
      setAlertMessage(`¡Pedido convertido a Factura ${res.data.formatted_folio}! Se descargó el inventario y se evaluó el costo PEPS/Promedio.`);
      fetchSalesData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al convertir pedido a factura.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleStamp = async (invoiceId: string) => {
    setActionLoading(invoiceId);
    setAlertMessage(null);
    try {
      const res = await apiClient.post<SalesDocItem>(`/sales/documents/${invoiceId}/stamp`);
      setAlertMessage(`¡Factura ${res.data.formatted_folio} timbrada exitosamente con UUID: ${res.data.cfdi_uuid}!`);
      fetchSalesData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al timbrar factura CFDI 4.0.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDownloadXml = async (doc: SalesDocItem) => {
    try {
      const response = await apiClient.get(`/sales/documents/${doc.id}/xml`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${doc.formatted_folio}_CFDI.xml`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al descargar XML.');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'TIMBRADO':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            TIMBRADO CFDI
          </span>
        );
      case 'SURTIDO':
      case 'APROBADO':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            {status}
          </span>
        );
      case 'PENDIENTE':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            PENDIENTE
          </span>
        );
      case 'CANCELADO':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            CANCELADO
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600">
            {status}
          </span>
        );
    }
  };

  const filteredDocs = documents.filter((d) => {
    const matchesSearch =
      d.formatted_folio.toLowerCase().includes(search.toLowerCase()) ||
      d.customer_name.toLowerCase().includes(search.toLowerCase());
    const matchesType = !docTypeFilter || d.document_type === docTypeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6">
      {/* KPI Metrics Dashboard Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Ventas del Mes</span>
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">
              ${metrics ? Number(metrics.monthly_sales_total).toLocaleString('es-MX', { minimumFractionDigits: 2 }) : '0.00'}
            </span>
            <span className="text-xs text-slate-400 ml-1">MXN</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">Facturación & Remisiones activas</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">CFDI 4.0 Timbrados</span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <FileCheck2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">
              {metrics ? metrics.stamped_invoices_count : '0'}
            </span>
            <span className="text-xs text-slate-400 ml-1">Comprobantes</span>
          </div>
          <div className="mt-2 text-[11px] text-emerald-600 font-medium">Con Sello Digital CSD y UUID</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Pedidos por Surtir</span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-amber-600">
              {metrics ? metrics.pending_orders_count : '0'}
            </span>
            <span className="text-xs text-slate-400 ml-1">Pedidos</span>
          </div>
          <div className="mt-2 text-[11px] text-amber-600 font-medium">Con reserva de inventario activa</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Ticket Promedio</span>
            <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">
              ${metrics ? Number(metrics.average_ticket).toLocaleString('es-MX', { minimumFractionDigits: 2 }) : '0.00'}
            </span>
            <span className="text-xs text-slate-400 ml-1">MXN</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">Promedio por operación</div>
        </div>
      </div>

      {/* Top 5 Products Strip */}
      {metrics && metrics.top_products.length > 0 && (
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-soft">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-3">
            Top 5 Productos Más Vendidos
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
            {metrics.top_products.map((p, idx) => (
              <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs">
                <span className="font-mono text-[10px] text-blue-600 font-bold block">{p.sku}</span>
                <span className="font-semibold text-slate-800 truncate block mt-0.5">{p.description}</span>
                <div className="mt-2 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">{p.units_sold} uds</span>
                  <span className="font-bold text-slate-900">${p.revenue.toLocaleString('es-MX')}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {alertMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{alertMessage}</span>
        </div>
      )}

      {/* Search and Filters */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-soft flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar por folio o cliente..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={docTypeFilter}
            onChange={(e) => setDocTypeFilter(e.target.value)}
            className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700"
          >
            <option value="">Todos los Documentos</option>
            <option value="FACTURA">Facturas (CFDI 4.0)</option>
            <option value="PEDIDO">Pedidos de Venta</option>
            <option value="REMISION">Remisiones</option>
            <option value="COTIZACION">Cotizaciones</option>
          </select>

          <button
            onClick={fetchSalesData}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl"
            title="Refrescar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-5 py-4">Documento & Folio</th>
                <th className="px-5 py-4">Fecha</th>
                <th className="px-5 py-4">Cliente Receptor</th>
                <th className="px-5 py-4 text-center">Estado</th>
                <th className="px-5 py-4 text-right">Subtotal</th>
                <th className="px-5 py-4 text-right">IVA (16%)</th>
                <th className="px-5 py-4 text-right font-bold text-slate-900">Total</th>
                <th className="px-5 py-4 text-center">Folio Fiscal UUID</th>
                <th className="px-5 py-4 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={9} className="text-center py-10 text-slate-400">
                    Cargando documentos comerciales y fiscales...
                  </td>
                </tr>
              ) : filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-10 text-slate-400">
                    No hay documentos de ventas registrados.
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="font-bold text-slate-900">{doc.document_type}</div>
                      <div className="text-[11px] font-mono text-blue-600 font-bold">{doc.formatted_folio}</div>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 font-mono">
                      {new Date(doc.created_at).toLocaleDateString('es-MX')}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-800">{doc.customer_name}</div>
                      <div className="text-[10px] font-mono text-slate-400">RFC: {doc.customer_rfc}</div>
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      {getStatusBadge(doc.status)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-slate-600">
                      ${Number(doc.subtotal).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-slate-600">
                      ${Number(doc.tax_iva_total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-slate-900">
                      ${Number(doc.total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3.5 text-center font-mono text-[10px]">
                      {doc.cfdi_uuid ? (
                        <span className="text-slate-600 bg-slate-100 px-2 py-0.5 rounded" title={doc.cfdi_uuid}>
                          {doc.cfdi_uuid.slice(0, 8)}...
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Convert to Invoice (for Pedidos) */}
                        {doc.document_type === 'PEDIDO' && doc.status === 'APROBADO' && (
                          <button
                            onClick={() => handleConvertToInvoice(doc.id)}
                            disabled={actionLoading === doc.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-lg text-[11px] font-semibold transition-colors disabled:opacity-50"
                            title="Convertir a Factura y descargar inventario"
                          >
                            <span>Facturar</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}

                        {/* Stamp Button (for pending Facturas) */}
                        {doc.document_type === 'FACTURA' && doc.status === 'PENDIENTE' && (
                          <button
                            onClick={() => handleStamp(doc.id)}
                            disabled={actionLoading === doc.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-semibold shadow-sm transition-colors disabled:opacity-50"
                          >
                            <Zap className="w-3 h-3" />
                            <span>{actionLoading === doc.id ? 'Sellando...' : 'Timbrar CFDI'}</span>
                          </button>
                        )}

                        {/* Download XML Button */}
                        {doc.status === 'TIMBRADO' && (
                          <button
                            onClick={() => handleDownloadXml(doc)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg text-[11px] font-semibold transition-colors"
                            title="Descargar XML CFDI 4.0 timbrado"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>XML</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

