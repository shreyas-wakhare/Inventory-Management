import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { StockMovementModuleStatus } from "../types/stock-movements.types";

export const stockMovementService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<StockMovementModuleStatus>>("/stock-movements/status", { token }),
};