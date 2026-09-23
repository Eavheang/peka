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

export interface UserResponse {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
}
