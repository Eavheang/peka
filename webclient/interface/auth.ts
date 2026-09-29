export interface LoginFormValues {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export type UserRole = "admin" | "senior" | "staff";

export interface InvitationSummary {
  id: string;
  email: string;
  role: UserRole;
  expires_at: string;
  created_at: string;
}

export interface InvitationResponse extends InvitationSummary {
  invite_url: string;
  email_sent: boolean;
}

export interface InvitationPreview {
  email: string;
  role: UserRole;
}

export interface AcceptInvitationRequest {
  token: string;
  display_name: string;
  password: string;
}

export interface UserResponse {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
}
