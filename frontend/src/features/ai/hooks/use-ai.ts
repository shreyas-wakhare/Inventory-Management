"use client";

import { aiService } from "../services/ai.service";

/**
 * Placeholder hook for the ai domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useAI() {
  return {
    service: aiService,
  };
}