"use client";

import { itemService } from "../services/items.service";

/**
 * Placeholder hook for the items domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useItem() {
  return {
    service: itemService,
  };
}