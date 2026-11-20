"use client";

import { deliveryOrderService } from "../services/delivery-orders.service";

/**
 * Placeholder hook for the delivery-orders domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useDeliveryOrder() {
  return {
    service: deliveryOrderService,
  };
}