"use client";

import { reconciliationService } from "../services/reconciliation.service";

/**
 * Placeholder hook for the reconciliation domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useReconciliation() {
  return {
    service: reconciliationService,
  };
}