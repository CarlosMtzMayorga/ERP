import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  ShieldCheck,
  Upload,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  Lock,
  FileKey,
  Calendar,
  Building,
  KeyRound,
  Trash2,
  RefreshCw,
} from 'lucide-react';

interface CSDItem {
  id: string;
  rfc: string;
  certificate_number: string;
  valid_from: string;
  valid_to: string;
  is_active: boolean;
  status: 'active' | 'expiring_soon' | 'expired' | 'not_yet_valid';
  days_remaining: number;
}

export const CSDTab: React.FC = () => {
  const [certificates, setCertificates] = useState<CSDItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // Upload form state
  const [cerFile, setCerFile] = useState<File | null>(null);
  const [keyFile, setKeyFile] = useState<File | null>(null);
  const [passphrase, setPassphrase] = useState('');
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchCertificates = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<CSDItem[]>('/config/csd');
      setCertificates(res.data);
    } catch (err) {
      console.error('Error fetching CSD:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCertificates();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cerFile || !keyFile || !passphrase) {
      setErrorMessage('Todos los campos son obligatorios (.cer, .key y contraseña).');
      return;
    }

    setUploading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append('cer_file', cerFile);
    formData.append('key_file', keyFile);
    formData.append('passphrase', passphrase);

    try {
      const res = await apiClient.post<CSDItem>('/config/csd/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSuccessMessage(`Certificado No. ${res.data.certificate_number} validado y activado exitosamente.`);
      setCerFile(null);
      setKeyFile(null);
      setPassphrase('');
      setIsModalOpen(false);
      fetchCertificates();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Error al validar par de certificados SAT.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('¿Está seguro de eliminar este certificado CSD? La facturación se detendrá si no hay otro activo.')) {
      return;
    }
    try {
      await apiClient.delete(`/config/csd/${id}`);
      fetchCertificates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al eliminar certificado.');
    }
  };

  const getStatusBadge = (status: CSDItem['status'], days: number) => {
    if (status === 'active') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          <span>Vigente ({days} días restantes)</span>
        </span>
      );
    }
    if (status === 'expiring_soon') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 animate-bounce" />
          <span>Próximo a Vencer ({days} días)</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
        <XCircle className="w-3.5 h-3.5 text-rose-600" />
        <span>Vencido</span>
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header with CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-soft">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-600" />
            <span>Certificados de Sello Digital (CSD SAT)</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Gestión criptográfica para el timbrado de facturas CFDI 4.0, nóminas y complementos de pago.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchCertificates}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
            title="Refrescar lista"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => {
              setErrorMessage(null);
              setIsModalOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 transition-all cursor-pointer"
          >
            <Upload className="w-4 h-4" />
            <span>Cargar Certificado (.cer y .key)</span>
          </button>
        </div>
      </div>

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Cards Grid */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 text-xs">Cargando certificados CSD...</div>
      ) : certificates.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-2xl border border-dashed border-slate-300">
          <FileKey className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-700">Sin Certificados CSD Registrados</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
            Para emitir y timbrar comprobantes fiscales digitales ante el SAT es indispensable cargar sus archivos .cer y .key.
          </p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-semibold"
          >
            Cargar CSD Ahora
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {certificates.map((csd) => (
            <div
              key={csd.id}
              className={`bg-white p-6 rounded-2xl border transition-all ${
                csd.is_active
                  ? 'border-blue-200 shadow-md ring-1 ring-blue-500/10'
                  : 'border-slate-200 shadow-soft opacity-75'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">
                      No. Serie: {csd.certificate_number}
                    </span>
                    {csd.is_active && (
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-50 text-blue-700">
                        Predeterminado
                      </span>
                    )}
                  </div>
                  <div className="text-xs font-semibold text-slate-700 mt-2 flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-slate-400" />
                    <span>RFC Titular: {csd.rfc}</span>
                  </div>
                </div>
                <div>{getStatusBadge(csd.status, csd.days_remaining)}</div>
              </div>

              {/* Dates & Validity Box */}
              <div className="mt-5 p-3.5 bg-slate-50 rounded-xl border border-slate-100 space-y-2 text-xs">
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Vigencia Inicial:</span>
                  </span>
                  <span className="font-medium text-slate-800">
                    {new Date(csd.valid_from).toLocaleDateString('es-MX')}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Vigencia Final:</span>
                  </span>
                  <span className="font-medium text-slate-800">
                    {new Date(csd.valid_to).toLocaleDateString('es-MX')}
                  </span>
                </div>
              </div>

              {/* Security Banner & Delete */}
              <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-400 font-mono text-[11px]">
                  <Lock className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Llave Cifrada AES-256</span>
                </span>
                <button
                  onClick={() => handleDelete(csd.id)}
                  className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition-colors"
                  title="Eliminar certificado"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-card border border-slate-100 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Cargar Certificados CSD SAT</h3>
                  <p className="text-xs text-slate-500">Validados y encriptados en memoria con AES-256</p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            {errorMessage && (
              <div className="mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleUpload} className="mt-5 space-y-4">
              {/* .CER File */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Certificado Público (.cer)
                </label>
                <input
                  type="file"
                  accept=".cer"
                  required
                  onChange={(e) => setCerFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer border border-slate-200 rounded-xl p-1"
                />
              </div>

              {/* .KEY File */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Llave Privada (.key)
                </label>
                <input
                  type="file"
                  accept=".key"
                  required
                  onChange={(e) => setKeyFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer border border-slate-200 rounded-xl p-1"
                />
              </div>

              {/* Passphrase */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Contraseña de la Llave Privada
                </label>
                <input
                  type="password"
                  required
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  placeholder="Contraseña establecida en Certifica SAT"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition-all"
                />
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
                  disabled={uploading}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 disabled:opacity-50"
                >
                  {uploading ? 'Validando criptografía...' : 'Validar y Guardar CSD'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
