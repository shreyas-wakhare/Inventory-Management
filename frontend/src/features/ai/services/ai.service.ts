import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { AIModuleStatus } from "../types/ai.types";

export const aiService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<AIModuleStatus>>("/ai/status", { token }),
};