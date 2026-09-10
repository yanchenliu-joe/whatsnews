import type { SavedArticle } from "../types";
import { devLog } from "../utils/devLog";
import {
  deleteRemoteSavedArticle,
  fetchRemoteSavedArticles,
  saveRemoteSavedArticle,
  type RemoteSavedArticle,
} from "./bookmarksApi";

export type BookmarkSyncStatus = "off" | "syncing" | "synced" | "error";

function remoteToLocal(remote: RemoteSavedArticle): SavedArticle {
  return {
    url: remote.article_url,
    title: remote.article_title ?? "",
    source: remote.source ?? "",
    topic: remote.topic ?? undefined,
    summary: remote.summary ?? undefined,
    why_it_matters: remote.why_it_matters ?? undefined,
    image_url: remote.image_url ?? undefined,
    saved_at: remote.saved_at ?? undefined,
    article_id: remote.article_id ?? undefined,
    remote_id: remote.id,
  };
}

function pickNewer(local: SavedArticle, remote: SavedArticle): SavedArticle {
  const localTime = local.saved_at ? new Date(local.saved_at).getTime() : 0;
  const remoteTime = remote.saved_at ? new Date(remote.saved_at).getTime() : 0;
  const newer = remoteTime >= localTime ? remote : local;
  const older = newer === remote ? local : remote;

  return {
    url: newer.url,
    title: newer.title || older.title,
    source: newer.source || older.source,
    topic: newer.topic ?? older.topic,
    summary: newer.summary ?? older.summary,
    why_it_matters: newer.why_it_matters ?? older.why_it_matters,
    image_url: newer.image_url ?? older.image_url,
    saved_at: newer.saved_at ?? older.saved_at,
    article_id: newer.article_id ?? older.article_id,
    remote_id: newer.remote_id ?? older.remote_id,
  };
}

export function mergeSavedArticles(
  local: SavedArticle[],
  remote: RemoteSavedArticle[],
): SavedArticle[] {
  const byUrl = new Map<string, SavedArticle>();

  for (const article of local) {
    if (!article.url) continue;
    byUrl.set(article.url, article);
  }

  for (const remoteItem of remote) {
    const mapped = remoteToLocal(remoteItem);
    const existing = byUrl.get(mapped.url);
    byUrl.set(mapped.url, existing ? pickNewer(existing, mapped) : mapped);
  }

  return [...byUrl.values()].sort((a, b) => {
    const aTime = a.saved_at ? new Date(a.saved_at).getTime() : 0;
    const bTime = b.saved_at ? new Date(b.saved_at).getTime() : 0;
    return bTime - aTime;
  });
}

/**
 * Sync local bookmarks with the server.
 *
 * Bidirectional deletion support:
 * - Pass `lastKnownRemoteUrls` (the remote URL set from the previous successful
 *   sync) so the function can detect URLs that were deleted on another device.
 *   Remotely-deleted items are filtered from the upload list (preventing
 *   resurrection) and returned in `remotelyDeletedUrls` for the caller to
 *   remove from local state.
 * - `currentRemoteUrls` is returned so the caller can persist it for the next
 *   sync's `lastKnownRemoteUrls`.
 */
export async function syncBookmarksWithServer(
  accessToken: string,
  localArticles: SavedArticle[],
  lastKnownRemoteUrls?: Set<string>,
): Promise<{
  merged: SavedArticle[];
  currentRemoteUrls: Set<string>;
  remotelyDeletedUrls: Set<string>;
  uploadedCount: number;
  downloadedCount: number;
}> {
  devLog("bookmarks", "sync_started");

  const remote = await fetchRemoteSavedArticles(accessToken);
  const currentRemoteUrls = new Set(remote.map((item) => item.article_url));

  // Detect remote deletions: URLs known to be on the server last sync that are
  // now absent. These were deleted on another device and must NOT be re-uploaded.
  const remotelyDeletedUrls = new Set<string>();
  if (lastKnownRemoteUrls && lastKnownRemoteUrls.size > 0) {
    for (const url of lastKnownRemoteUrls) {
      if (!currentRemoteUrls.has(url)) {
        remotelyDeletedUrls.add(url);
      }
    }
  }

  // Exclude remotely-deleted items from local before merge so they are not
  // re-uploaded and do not appear in the merged output.
  const filteredLocal =
    remotelyDeletedUrls.size > 0
      ? localArticles.filter((a) => !a.url || !remotelyDeletedUrls.has(a.url))
      : localArticles;

  const merged = mergeSavedArticles(filteredLocal, remote);

  let uploadedCount = 0;
  for (const article of merged) {
    if (currentRemoteUrls.has(article.url)) {
      continue;
    }
    await saveRemoteSavedArticle(accessToken, article);
    uploadedCount += 1;
  }

  const downloadedCount = remote.length;
  devLog("bookmarks", "sync_uploaded_count", { count: uploadedCount });
  devLog("bookmarks", "sync_downloaded_count", { count: downloadedCount });
  if (remotelyDeletedUrls.size > 0) {
    devLog("bookmarks", "sync_remote_deletions_detected", {
      count: remotelyDeletedUrls.size,
    });
  }

  return { merged, currentRemoteUrls, remotelyDeletedUrls, uploadedCount, downloadedCount };
}

export async function pushSavedArticleToServer(
  accessToken: string,
  article: SavedArticle,
): Promise<void> {
  await saveRemoteSavedArticle(accessToken, article);
}

export async function removeSavedArticleFromServer(
  accessToken: string,
  url: string,
): Promise<void> {
  await deleteRemoteSavedArticle(accessToken, url);
}

export function logSyncFailed(message: string): void {
  devLog("bookmarks", "sync_failed", { reason: message.slice(0, 120) });
}
