import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { DeliveryOrderModuleStatus } from "../types/delivery-orders.types";

export const deliveryOrderService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<DeliveryOrderModuleStatus>>("/delivery-orders/status", { token }),
};