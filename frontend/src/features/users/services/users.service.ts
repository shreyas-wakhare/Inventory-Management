import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { UserModuleStatus } from "../types/users.types";

export const userService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<UserModuleStatus>>("/users/status", { token }),
};