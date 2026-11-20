import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { CollectionOrderModuleStatus } from "../types/collection-orders.types";

export const collectionOrderService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<CollectionOrderModuleStatus>>("/collection-orders/status", { token }),
};