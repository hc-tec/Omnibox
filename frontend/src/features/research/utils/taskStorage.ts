const QUERY_KEY_PREFIX = "research:task";
const QUERY_KEY_SUFFIX = ":query";

function getQueryKey(taskId: string): string {
  return `${QUERY_KEY_PREFIX}:${taskId}${QUERY_KEY_SUFFIX}`;
}

function safeSessionStorage(): Storage | null {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  return window.sessionStorage;
}

export function persistResearchTaskQuery(taskId: string, query: string): void {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.setItem(getQueryKey(taskId), query);
  } catch {
    // ignore quota / privacy errors
  }
}

export function loadResearchTaskQuery(taskId: string): string | null {
  const storage = safeSessionStorage();
  if (!storage) return null;
  try {
    return storage.getItem(getQueryKey(taskId));
  } catch {
    return null;
  }
}

export function clearResearchTaskQuery(taskId: string): void {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.removeItem(getQueryKey(taskId));
  } catch {
    // ignore
  }
}
