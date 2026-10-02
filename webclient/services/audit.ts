import { useInfiniteQuery } from "@tanstack/react-query";
import axios from "axios";

import type { AuditEventType, AuditEventsResponse } from "@/interface/audit";
import axiosInstance from "@/utils/axios";

export function isAuditEventsForbidden(error: unknown) {
  return axios.isAxiosError(error) && error.response?.status === 403;
}

export const useListAuditEvents = ({
  type,
  enabled = true,
}: {
  type?: AuditEventType;
  enabled?: boolean;
} = {}) =>
  useInfiniteQuery({
    queryKey: ["audit-events", "list", type ?? "all"],
    enabled,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }) => {
      const params: Record<string, string> = {};
      if (type) params.type = type;
      if (pageParam) params.cursor = pageParam;
      return (
        await axiosInstance.get<AuditEventsResponse>("/admin/audit-events", {
          params,
          signal,
        })
      ).data;
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    retry: (failureCount, error) => failureCount < 3 && !isAuditEventsForbidden(error),
  });
