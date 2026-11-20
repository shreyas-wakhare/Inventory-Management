import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { ItemModuleStatus } from "../types/items.types";

export const itemService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<ItemModuleStatus>>("/items/status", { token }),
};