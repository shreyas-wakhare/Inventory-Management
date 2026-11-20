"use client";

import { stockMovementService } from "../services/stock-movements.service";

/**
 * Placeholder hook for the stock-movements domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useStockMovement() {
  return {
    service: stockMovementService,
  };
}