import React, { useState, useEffect } from 'react';
import { apiClient } from '../../../api/axiosClient';
import {
  Users,
  UserPlus,
  Shield,
  CheckCircle,
  XCircle,
  Building,
  Key,
  RefreshCw,
  Search,
  Check,
  ChevronRight,
} from 'lucide-react';

interface TenantUserItem {
  id: string;              // User ID
  tenant_user_id: string;
  email: string;
  full_name: string;
  phone?: string;
  is_active: boolean;
  default_branch_id?: string;
  default_branch_name?: string;
  roles: string[];
  role_ids: string[];
}

interface RoleItem {
  id: string;
  code: string;
  name: string;
  description?: string;
  is_system: boolean;
}

interface PermissionItem {
  id: string;
  module: string;
  action: string;
  code: string;
  description?: string;
}

interface BranchItem {
  id: string;
  code: string;
  name: string;
}

export const UsersTab: React.FC = () => {
  const [users, setUsers] = useState<TenantUserItem[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [permissionsGrouped, setPermissionsGrouped] = useState<Record<string, PermissionItem[]>>({});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [isCreateUserModalOpen, setIsCreateUserModalOpen] = useState(false);
  const [isRolesModalOpen, setIsRolesModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<TenantUserItem | null>(null);

  // New User Form State
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserName, setNewUserName] = useState('');
  const [newUserPhone, setNewUserPhone] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('Temporal123!*');
  const [newUserBranchId, setNewUserBranchId] = useState('');
  const [newUserRoleIds, setNewUserRoleIds] = useState<string[]>([]);

  // Edit Roles State
  const [editRoleIds, setEditRoleIds] = useState<string[]>([]);
  const [editBranchId, setEditBranchId] = useState<string>('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [usersRes, rolesRes, branchesRes, permsRes] = await Promise.all([
        apiClient.get<TenantUserItem[]>('/rbac/users'),
        apiClient.get<RoleItem[]>('/rbac/roles'),
        apiClient.get<BranchItem[]>('/tenants/branches'),
        apiClient.get<Record<string, PermissionItem[]>>('/rbac/permissions'),
      ]);
      setUsers(usersRes.data);
      setRoles(rolesRes.data);
      setBranches(branchesRes.data);
      setPermissionsGrouped(permsRes.data);
    } catch (err) {
      console.error('Error fetching RBAC data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.post('/rbac/users', {
        email: newUserEmail,
        full_name: newUserName,
        phone: newUserPhone || null,
        password: newUserPassword,
        default_branch_id: newUserBranchId || null,
        role_ids: newUserRoleIds,
      });
      setIsCreateUserModalOpen(false);
      setNewUserEmail('');
      setNewUserName('');
      setNewUserRoleIds([]);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al registrar usuario.');
    }
  };

  const handleToggleStatus = async (user: TenantUserItem) => {
    const newStatus = !user.is_active;
    try {
      await apiClient.put(`/rbac/users/${user.id}/status?active=${newStatus}`);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al cambiar estado del usuario.');
    }
  };

  const openEditRolesModal = (user: TenantUserItem) => {
    setSelectedUser(user);
    setEditRoleIds(user.role_ids || []);
    setEditBranchId(user.default_branch_id || '');
    setIsRolesModalOpen(true);
  };

  const handleSaveRoles = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await apiClient.put(`/rbac/users/${selectedUser.id}/roles`, {
        role_ids: editRoleIds,
        default_branch_id: editBranchId || null,
      });
      setIsRolesModalOpen(false);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al actualizar roles.');
    }
  };

  const filteredUsers = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-soft">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-600" />
            <span>Usuarios y Control de Acceso (RBAC)</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Gestión de usuarios por empresa con asignación granular de roles y facultades operativas.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
            title="Refrescar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsCreateUserModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 transition-all cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            <span>Asignar / Nuevo Usuario</span>
          </button>
        </div>
      </div>

      {/* Filter and Table Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-soft overflow-hidden">
        {/* Search bar */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="relative w-full max-w-sm">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar por nombre o correo..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
          <span className="text-xs text-slate-500 font-medium">
            Total: {filteredUsers.length} colaboradores
          </span>
        </div>

        {/* Users Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-6 py-4">Usuario</th>
                <th className="px-6 py-4">Sucursal Asignada</th>
                <th className="px-6 py-4">Roles en Empresa</th>
                <th className="px-6 py-4 text-center">Estado</th>
                <th className="px-6 py-4 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    Cargando usuarios...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    No se encontraron usuarios.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-sm shadow-sm">
                          {u.full_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-bold text-slate-900">{u.full_name}</div>
                          <div className="text-[11px] text-slate-500">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 text-slate-700">
                        <Building className="w-3.5 h-3.5 text-slate-400" />
                        <span>{u.default_branch_name || 'Sin sucursal'}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        {u.roles.length > 0 ? (
                          u.roles.map((r, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200/60 font-semibold text-[10px]"
                            >
                              {r}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-400 text-[11px]">Sin roles asignados</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleToggleStatus(u)}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold border transition-colors cursor-pointer ${
                          u.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                            : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
                        }`}
                        title="Clic para cambiar estado"
                      >
                        {u.is_active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        <span>{u.is_active ? 'Activo' : 'Suspendido'}</span>
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => openEditRolesModal(u)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-[11px] font-semibold transition-colors"
                      >
                        <Shield className="w-3.5 h-3.5 text-slate-500" />
                        <span>Gestionar Roles</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Nuevo Usuario */}
      {isCreateUserModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-8 shadow-card border border-slate-100 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Asignar Usuario a la Empresa</h3>
              <button onClick={() => setIsCreateUserModalOpen(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <form onSubmit={handleCreateUser} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Correo Electrónico
                </label>
                <input
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="usuario@empresa.com"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Nombre Completo
                </label>
                <input
                  type="text"
                  required
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  placeholder="Juan Pérez"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Sucursal por Defecto
                </label>
                <select
                  value={newUserBranchId}
                  onChange={(e) => setNewUserBranchId(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                >
                  <option value="">Seleccionar sucursal</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.code} - {b.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Roles a Asignar
                </label>
                <div className="space-y-1.5 max-h-36 overflow-y-auto p-2 border border-slate-200 rounded-xl bg-slate-50">
                  {roles.map((r) => (
                    <label key={r.id} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newUserRoleIds.includes(r.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setNewUserRoleIds([...newUserRoleIds, r.id]);
                          } else {
                            setNewUserRoleIds(newUserRoleIds.filter((id) => id !== r.id));
                          }
                        }}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span>{r.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateUserModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20"
                >
                  Guardar Usuario
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Editar Roles */}
      {isRolesModalOpen && selectedUser && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-card border border-slate-100 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">Gestionar Roles y Sucursal</h3>
                <p className="text-xs text-slate-500">{selectedUser.full_name} ({selectedUser.email})</p>
              </div>
              <button onClick={() => setIsRolesModalOpen(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <form onSubmit={handleSaveRoles} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Sucursal por Defecto
                </label>
                <select
                  value={editBranchId}
                  onChange={(e) => setEditBranchId(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                >
                  <option value="">Sin sucursal asignada</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.code} - {b.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Roles Asignados
                </label>
                <div className="space-y-2 p-3 bg-slate-50 rounded-xl border border-slate-200">
                  {roles.map((r) => (
                    <label key={r.id} className="flex items-start gap-2.5 text-xs text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editRoleIds.includes(r.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setEditRoleIds([...editRoleIds, r.id]);
                          } else {
                            setEditRoleIds(editRoleIds.filter((id) => id !== r.id));
                          }
                        }}
                        className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                      />
                      <div>
                        <div className="font-semibold text-slate-900">{r.name}</div>
                        <div className="text-[11px] text-slate-500">{r.description || 'Sin descripción'}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsRolesModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20"
                >
                  Actualizar Accesos
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
