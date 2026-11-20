export interface ApiResponse<T> {
  data: T;
  message: string;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
  };
}

