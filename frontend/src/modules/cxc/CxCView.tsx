import React, { useState, useEffect } from 'react';
import { apiClient } from '../../api/axiosClient';
import { CxCDashboardData, PaymentReceiptSummary } from './types';
import { CxCDashboardTab } from './components/CxCDashboardTab';
import { PaymentApplicationTab } from './components/PaymentApplicationTab';
import { AccountStatementTab } from './components/AccountStatementTab';
import { PaymentReceiptModal } from './components/PaymentReceiptModal';
import {
  CreditCard,
  LayoutDashboard,
  FileText,
  History,
  RotateCcw,
  CheckCircle2,
  Printer,
  ShieldCheck
} from 'lucide-react';

export const CxCView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'payment' | 'statement' | 'history'>('dashboard');
  const [dashboardData, setDashboardData] = useState<CxCDashboardData | null>(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState<boolean>(true);

  // Selected customer for cross-tab jumps
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');

  // History Tab state
  const [paymentsList, setPaymentsList] = useState<PaymentReceiptSummary[]>([]);
  const [isLoadingPayments, setIsLoadingPayments] = useState<boolean>(false);

  // Success modal
  const [recentReceipt, setRecentReceipt] = useState<any | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  useEffect(() => {
    if (activeTab === 'history') {
      loadPaymentsHistory();
    }
  }, [activeTab]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadDashboard = async () => {
    setIsLoadingDashboard(true);
    try {
      const res = await apiClient.get<CxCDashboardData>('/cxc/dashboard');
      setDashboardData(res.data);
    } catch (e) {
      console.error('Error loading CxC dashboard:', e);
    } finally {
      setIsLoadingDashboard(false);
    }
  };

  const loadPaymentsHistory = async () => {
    setIsLoadingPayments(true);
    try {
      const res = await apiClient.get<PaymentReceiptSummary[]>('/cxc/payments');
      setPaymentsList(res.data);
    } catch (e) {
      console.error('Error loading payments history:', e);
    } finally {
      setIsLoadingPayments(false);
    }
  };

  const handleSelectCustomerForStatement = (customerId: string) => {
    setSelectedCustomerId(customerId);
    setActiveTab('statement');
  };

  const handlePaymentSuccess = (receipt: any) => {
    setRecentReceipt(receipt);
    showToast('¡Complemento de Pago REP 2.0 timbrado y aplicado!');
    loadDashboard();
  };

  return (
    <div className="flex flex-col space-y-5">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 right-8 z-50 bg-emerald-600 text-white px-4 py-2.5 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-bold animate-in fade-in slide-in-from-top-4">
          <CheckCircle2 className="w-4 h-4" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* TOP MODULE HEADER */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 bg-indigo-700 text-white rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-600/20">
            <CreditCard className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                Cuentas por Cobrar (CxC)
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                REP 2.0 • CFDI 4.0
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Control de Crédito, Antigüedad de Saldos Contable y Complemento de Pagos SAT
            </p>
          </div>
        </div>

        <button
          onClick={loadDashboard}
          className="py-2 px-3 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Actualizar Datos</span>
        </button>
      </div>

      {/* TABS NAVIGATION */}
      <div className="flex border-b border-slate-200 space-x-1">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`py-2.5 px-4 text-xs font-bold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'dashboard'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Dashboard & Antigüedad</span>
        </button>

        <button
          onClick={() => setActiveTab('payment')}
          className={`py-2.5 px-4 text-xs font-bold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'payment'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Aplicación de Pagos (REP 2.0)</span>
        </button>

        <button
          onClick={() => setActiveTab('statement')}
          className={`py-2.5 px-4 text-xs font-bold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'statement'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Estado de Cuenta por Cliente</span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`py-2.5 px-4 text-xs font-bold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'history'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Historial de Pagos Timbrados</span>
        </button>
      </div>

      {/* TAB CONTENTS */}
      {activeTab === 'dashboard' && (
        <CxCDashboardTab
          data={dashboardData}
          isLoading={isLoadingDashboard}
          onSelectCustomer={handleSelectCustomerForStatement}
          onGoToPayment={() => setActiveTab('payment')}
        />
      )}

      {activeTab === 'payment' && (
        <PaymentApplicationTab
          initialCustomerId={selectedCustomerId}
          onPaymentSuccess={handlePaymentSuccess}
        />
      )}

      {activeTab === 'statement' && (
        <AccountStatementTab initialCustomerId={selectedCustomerId} />
      )}

      {activeTab === 'history' && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Historial de Recibos de Pago (REP 2.0)
              </h3>
              <p className="text-xs text-slate-500">
                Comprobantes fiscales de pago CFDI 4.0 con timbre fiscal digital del PAC
              </p>
            </div>
            <button
              onClick={loadPaymentsHistory}
              className="py-1.5 px-3 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-lg flex items-center space-x-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Refrescar</span>
            </button>
          </div>

          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Folio Recibo</th>
                  <th className="py-3 px-4">Fecha Pago</th>
                  <th className="py-3 px-4">Cliente</th>
                  <th className="py-3 px-4">Forma Pago</th>
                  <th className="py-3 px-4 text-center">Facturas Liquidadas</th>
                  <th className="py-3 px-4 text-right">Monto Total</th>
                  <th className="py-3 px-4">UUID SAT</th>
                  <th className="py-3 px-4 text-center">Estado</th>
                  <th className="py-3 px-4 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoadingPayments ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-slate-400">
                      Cargando recibos de pago...
                    </td>
                  </tr>
                ) : paymentsList.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-slate-400">
                      No se han emitido complementos de recepción de pago aún.
                    </td>
                  </tr>
                ) : (
                  paymentsList.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 font-bold text-slate-900">{p.folio}</td>
                      <td className="py-3 px-4 text-slate-500">
                        {new Date(p.payment_date).toLocaleString('es-MX')}
                      </td>
                      <td className="py-3 px-4 font-semibold text-slate-800">{p.customer_name}</td>
                      <td className="py-3 px-4 text-slate-700">{p.payment_form}</td>
                      <td className="py-3 px-4 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700">
                          {p.docs_count} doctos
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-black text-emerald-700">
                        ${Number(p.amount).toFixed(2)}
                      </td>
                      <td className="py-3 px-4 font-mono text-[10px] text-indigo-700 truncate max-w-[130px]">
                        {p.cfdi_uuid}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                          {p.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => setRecentReceipt(p)}
                          className="p-1 hover:bg-slate-100 rounded text-slate-600 hover:text-blue-600 transition"
                          title="Imprimir Comprobante"
                        >
                          <Printer className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RECEIPT MODAL */}
      <PaymentReceiptModal
        receipt={recentReceipt}
        isOpen={!!recentReceipt}
        onClose={() => setRecentReceipt(null)}
      />
    </div>
  );
};
export default CxCView;

