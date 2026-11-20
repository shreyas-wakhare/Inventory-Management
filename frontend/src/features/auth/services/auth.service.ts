import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { AuthModuleStatus } from "../types/auth.types";

export const authService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<AuthModuleStatus>>("/auth/status", { token }),
};