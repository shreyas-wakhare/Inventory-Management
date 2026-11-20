import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { ReconciliationModuleStatus } from "../types/reconciliation.types";

export const reconciliationService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<ReconciliationModuleStatus>>("/reconciliation/status", { token }),
};