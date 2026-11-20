"use client";

import { projectService } from "../services/projects.service";

/**
 * Placeholder hook for the projects domain.
 * State management and data fetching will be implemented in SDD-3.
 */
export function useProject() {
  return {
    service: projectService,
  };
}