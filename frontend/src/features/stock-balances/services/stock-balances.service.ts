import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { StockBalanceModuleStatus } from "../types/stock-balances.types";

export const stockBalanceService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<StockBalanceModuleStatus>>("/stock-balances/status", { token }),
};