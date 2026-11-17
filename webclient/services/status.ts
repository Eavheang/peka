import { useQuery } from "@tanstack/react-query";

import axiosInstance from "@/utils/axios";

type ServerStatus = {
  online: boolean;
  // Features an admin has set up. Each one also needs the server to be online.
  configured: { web_search: boolean; google_drive: boolean; email: boolean };
};

// Until the first answer arrives, nothing counts as offline or configured.
export const useServerStatus = () => {
  const { data } = useQuery({
    queryKey: ["status"],
    queryFn: async ({ signal }) =>
      (await axiosInstance.get<ServerStatus>("/status", { signal })).data,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  return { offline: data?.online === false, configured: data?.configured };
};
