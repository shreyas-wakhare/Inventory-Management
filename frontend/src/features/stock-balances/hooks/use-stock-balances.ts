"use client";

import { stockBalanceService } from "../services/stock-balances.service";

/**
 * Placeholder hook for the stock-balances domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useStockBalance() {
  return {
    service: stockBalanceService,
  };
}