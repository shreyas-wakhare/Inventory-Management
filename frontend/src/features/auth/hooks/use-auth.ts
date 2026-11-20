"use client";

import { authService } from "../services/auth.service";

/**
 * Placeholder hook for the auth domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useAuth() {
  return {
    service: authService,
  };
}