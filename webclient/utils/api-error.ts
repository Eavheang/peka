import axios from "axios";

// The message the API sent (FastAPI's `detail`), or the fallback when the error is not an API response
// with a text message (network failure, a proxy's HTML error page, a validation error list).
// Never the HTTP client's own text such as "Request failed with status code 409".
export function getApiErrorMessage(error: unknown, fallback: string): string {
  const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
  return typeof detail === "string" ? detail : fallback;
}
