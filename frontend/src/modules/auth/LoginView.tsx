import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/axiosClient';
import { TokenResponse } from '../../types/auth';
import { ShieldCheck, Lock, Mail, AlertCircle, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';

export const LoginView: React.FC = () => {
  const [email, setEmail] = useState('admin@erpsaas.com');
  const [password, setPassword] = useState('Admin123!*');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await apiClient.post<TokenResponse>('/auth/login', {
        email,
        password,
      });
      login(response.data);
      navigate('/dashboard');
    } catch (err: any) {
      console.error('Login error:', err);
      setError(
        err.response?.data?.detail || 'Error al iniciar sesión. Verifique sus credenciales.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-screen flex items-center justify-center bg-slate-900 px-4 py-12 relative overflow-hidden font-sans">
      {/* Background Emerald Ambient Glow */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-[#047857]/20 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-emerald-600/15 rounded-full blur-3xl pointer-events-none"></div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="w-full max-w-md bg-white dark:bg-gray-800 rounded-3xl shadow-2xl border border-gray-100 dark:border-gray-700/60 p-8 sm:p-10 relative z-10"
      >
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-[#047857] text-white rounded-2xl mx-auto flex items-center justify-center shadow-lg shadow-emerald-950/40 mb-4">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white tracking-tight">
            ERP SaaS Enterprise
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Sistema Multiempresa Cloud • SAT CFDI 4.0 • Anexo 24
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center space-x-2.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5 uppercase tracking-wider">
              Correo Electrónico
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@erpsaas.com"
                className="w-full pl-10 pr-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white rounded-xl text-xs placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#047857]/30 focus:border-[#047857] transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5 uppercase tracking-wider">
              Contraseña
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white rounded-xl text-xs placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#047857]/30 focus:border-[#047857] transition-all"
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-[#047857] hover:bg-emerald-800 active:scale-[0.98] text-white font-semibold rounded-xl text-xs shadow-md shadow-emerald-950/30 transition-all flex items-center justify-center space-x-2 disabled:opacity-70 cursor-pointer"
            >
              {loading ? (
                <span>Validando sesión...</span>
              ) : (
                <span>Ingresar al Sistema</span>
              )}
            </button>
          </div>
        </form>

        <div className="mt-8 pt-6 border-t border-gray-100 dark:border-gray-700 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 flex items-center justify-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#047857]" />
            <span>Infraestructura Segura • Criptografía CSD en Memoria</span>
          </p>
        </div>
      </motion.div>
    </div>
  );
};
