"use client";

import { equipmentUnitService } from "../services/equipment-units.service";

/**
 * Placeholder hook for the equipment-units domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useEquipmentUnit() {
  return {
    service: equipmentUnitService,
  };
}