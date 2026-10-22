import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
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
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="space-y-6 max-w-7xl mx-auto font-sans"
    >
      {/* Module Title & Tab Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#047857]/10 dark:bg-[#047857]/20 text-[#047857] flex items-center justify-center">
              <ShoppingBag className="w-5 h-5 text-[#047857]" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">
              Módulo 6: Compras y Abastecimiento
            </h1>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Gestión del ciclo de compras, recepción física en almacén, valuación PEPS y pasivos con proveedores (CxP).
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchPurchasesData}
            disabled={loading}
            className="p-2.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:text-[#047857] dark:hover:text-emerald-400 rounded-xl text-xs font-semibold shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
            title="Actualizar datos"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs Menu with Emerald Accent */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 space-x-2 overflow-x-auto pb-px">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap cursor-pointer ${
            activeTab === 'dashboard'
              ? 'border-[#047857] text-[#047857] dark:text-emerald-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Dashboard de Compras</span>
        </button>

        <button
          onClick={() => setActiveTab('orders')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap cursor-pointer ${
            activeTab === 'orders'
              ? 'border-[#047857] text-[#047857] dark:text-emerald-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Órdenes de Compra ({orders.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('reception')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap cursor-pointer ${
            activeTab === 'reception'
              ? 'border-[#047857] text-[#047857] dark:text-emerald-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <PackageCheck className="w-4 h-4" />
          <span>Captura de Recepción</span>
        </button>

        <button
          onClick={() => setActiveTab('xml_import')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap cursor-pointer ${
            activeTab === 'xml_import'
              ? 'border-[#047857] text-[#047857] dark:text-emerald-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <UploadCloud className="w-4 h-4" />
          <span>Workspace Importación XML</span>
        </button>

        <button
          onClick={() => setActiveTab('payables')}
          className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors whitespace-nowrap cursor-pointer ${
            activeTab === 'payables'
              ? 'border-[#047857] text-[#047857] dark:text-emerald-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
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
    </motion.div>
  );
};

