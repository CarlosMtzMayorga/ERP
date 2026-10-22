import React, { useState, useEffect } from 'react';
import {
  PurchasesDashboardMetrics,
  PurchaseDocument,
  PayableDocument,
} from './types';
import { PurchasesDashboardTab } from './components/PurchasesDashboardTab';
import { PurchaseOrdersTab } from './components/PurchaseOrdersTab';
import { GoodsReceptionTab } from './components/GoodsReceptionTab';
import { XMLImporterTab } from './components/XMLImporterTab';
import { AccountsPayableTab } from './components/AccountsPayableTab';
import { apiClient } from '../../api/axiosClient';
import {
  ShoppingBag,
  LayoutDashboard,
  FileText,
  PackageCheck,
  UploadCloud,
  CreditCard,
  RefreshCw,
} from 'lucide-react';

export const PurchasesView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    'dashboard' | 'orders' | 'reception' | 'xml_import' | 'payables'
  >('dashboard');

  const [loading, setLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState<PurchasesDashboardMetrics | null>(null);
  const [orders, setOrders] = useState<PurchaseDocument[]>([]);
  const [recentDocs, setRecentDocs] = useState<PurchaseDocument[]>([]);
  const [payables, setPayables] = useState<PayableDocument[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [currencies, setCurrencies] = useState<any[]>([]);

  const [selectedPOForReception, setSelectedPOForReception] = useState<PurchaseDocument | null>(null);
  const [showCreatePOModal, setShowCreatePOModal] = useState<boolean>(false);

  const fetchPurchasesData = async () => {
    setLoading(true);
    try {
      const [
        metricsRes,
        ordersRes,
        allDocsRes,
        payablesRes,
        suppliersRes,
        productsRes,
        branchesRes,
        warehousesRes,
        currenciesRes,
      ] = await Promise.all([
        apiClient.get<PurchasesDashboardMetrics>('/purchases/dashboard').catch(() => ({ data: null })),
        apiClient.get<PurchaseDocument[]>('/purchases/documents?document_type=ORDEN_COMPRA').catch(() => ({ data: [] })),
        apiClient.get<PurchaseDocument[]>('/purchases/documents?limit=15').catch(() => ({ data: [] })),
        apiClient.get<PayableDocument[]>('/purchases/payables').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/tenants/suppliers').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/inventory/products').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/tenants/branches').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/inventory/warehouses').catch(() => ({ data: [] })),
        apiClient.get<any[]>('/tenants/currencies').catch(() => ({ data: [] })),
      ]);

      setMetrics(metricsRes.data);
      setOrders(ordersRes.data);
      setRecentDocs(allDocsRes.data);
      setPayables(payablesRes.data);
      setSuppliers(suppliersRes.data);
      setProducts(productsRes.data);
      setBranches(branchesRes.data);
      setWarehouses(warehousesRes.data);
      setCurrencies(currenciesRes.data);
    } catch (err) {
      console.error('Error fetching purchases data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPurchasesData();
  }, []);

  const handleCreateOrder = async (payload: any) => {
    await apiClient.post('/purchases/orders', payload);
    await fetchPurchasesData();
  };

  const handleAuthorizeOrder = async (orderId: string) => {
    await apiClient.put(`/purchases/orders/${orderId}/authorize`);
    await fetchPurchasesData();
  };

  const handleConfirmReception = async (payload: any) => {
    await apiClient.post('/purchases/receptions', payload);
    await fetchPurchasesData();
    setActiveTab('orders');
  };

  const handleSelectForReception = (po: PurchaseDocument) => {
    setSelectedPOForReception(po);
    setActiveTab('reception');
  };

  return (
    <div className="space-y-6">
      {/* Module Title & Tab Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 bg-blue-600 text-white rounded-xl shadow-md shadow-blue-500/20">
              <ShoppingBag className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
              Compras y Abastecimiento
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Gestión del ciclo de compras, recepción física en almacén, valuación PEPS y pasivos con proveedores (CxP).
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchPurchasesData}
            disabled={loading}
            className="p-2.5 bg-white border border-slate-200 text-slate-600 hover:text-blue-600 rounded-xl text-xs font-semibold shadow-2xs hover:bg-slate-50 transition-colors"
            title="Actualizar datos"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-slate-200 space-x-2 overflow-x-auto pb-px">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'dashboard'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Dashboard de Compras</span>
        </button>

        <button
          onClick={() => setActiveTab('orders')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'orders'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Órdenes de Compra ({orders.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('reception')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'reception'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <PackageCheck className="w-4 h-4" />
          <span>Captura de Recepción</span>
        </button>

        <button
          onClick={() => setActiveTab('xml_import')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'xml_import'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <UploadCloud className="w-4 h-4" />
          <span>Workspace Importación XML</span>
        </button>

        <button
          onClick={() => setActiveTab('payables')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap ${
            activeTab === 'payables'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Cuentas por Pagar ({payables.length})</span>
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'dashboard' && (
        <PurchasesDashboardTab
          metrics={metrics}
          recentDocs={recentDocs}
          onOpenCreatePO={() => {
            setActiveTab('orders');
            setShowCreatePOModal(true);
          }}
          onGoToReception={() => setActiveTab('reception')}
          onGoToXML={() => setActiveTab('xml_import')}
        />
      )}

      {activeTab === 'orders' && (
        <PurchaseOrdersTab
          orders={orders}
          suppliers={suppliers}
          products={products}
          branches={branches}
          warehouses={warehouses}
          currencies={currencies}
          onCreateOrder={handleCreateOrder}
          onAuthorizeOrder={handleAuthorizeOrder}
          onSelectForReception={handleSelectForReception}
          showCreateModal={showCreatePOModal}
          setShowCreateModal={setShowCreatePOModal}
        />
      )}

      {activeTab === 'reception' && (
        <GoodsReceptionTab
          activeOrders={orders.filter(
            (o) => o.status === 'AUTORIZADA' || o.status === 'PARCIALMENTE_RECIBIDA'
          )}
          selectedPO={selectedPOForReception}
          onSelectPO={setSelectedPOForReception}
          warehouses={warehouses}
          branches={branches}
          onConfirmReception={handleConfirmReception}
        />
      )}

      {activeTab === 'xml_import' && (
        <XMLImporterTab
          branches={branches}
          warehouses={warehouses}
          currencies={currencies}
          onImportComplete={fetchPurchasesData}
        />
      )}

      {activeTab === 'payables' && (
        <AccountsPayableTab payables={payables} />
      )}
    </div>
  );
};

