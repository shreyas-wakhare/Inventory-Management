"use client";

import { userService } from "../services/users.service";

/**
 * Placeholder hook for the users domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useUser() {
  return {
    service: userService,
  };
}