import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { ProjectModuleStatus } from "../types/projects.types";

export const projectService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<ProjectModuleStatus>>("/projects/status", { token }),
};