"use client";

import { collectionOrderService } from "../services/collection-orders.service";

/**
 * Placeholder hook for the collection-orders domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useCollectionOrder() {
  return {
    service: collectionOrderService,
  };
}