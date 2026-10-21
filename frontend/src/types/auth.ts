export interface TenantBrief {
  id: string;
  rfc: string;
  legal_name: string;
  trade_name?: string;
  default_branch_id?: string;
  roles: string[];
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  is_superadmin: boolean;
  is_active: boolean;
  tenants: TenantBrief[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: UserProfile;
  active_tenant_id?: string;
  active_branch_id?: string;
  permissions: string[];
}

