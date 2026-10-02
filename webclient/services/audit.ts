import { useInfiniteQuery } from "@tanstack/react-query";

import type { AuditEventType, AuditEventsResponse } from "@/interface/audit";
import axiosInstance from "@/utils/axios";

export const useListAuditEvents = ({ type }: { type?: AuditEventType }) =>
  useInfiniteQuery({
    queryKey: ["audit-events", "list", type ?? "all"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }) =>
      (
        await axiosInstance.get<AuditEventsResponse>("/admin/audit-events", {
          params: { type, cursor: pageParam },
          signal,
        })
      ).data,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });
