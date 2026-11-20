import { apiClient } from "@/lib/api-client";
import type { ApiResponse } from "@/types/api";
import type { EquipmentUnitModuleStatus } from "../types/equipment-units.types";

export const equipmentUnitService = {
  getStatus: (token?: string) =>
    apiClient.get<ApiResponse<EquipmentUnitModuleStatus>>("/equipment-units/status", { token }),
};