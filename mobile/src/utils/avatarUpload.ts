import { File } from "expo-file-system";

import { getSupabaseClientOrNull } from "../lib/supabase/client";

/**
 * Uploads a local image URI (from expo-image-picker) directly to the
 * "avatars" Supabase Storage bucket (migration 0025) and returns its public
 * URL. Object path is "{userId}/avatar.jpg" — upsert overwrites the
 * previous avatar rather than accumulating orphaned files per upload.
 *
 * Reads the file via expo-file-system's File.bytes() rather than
 * fetch(localUri).blob() — the latter silently produces a 0-byte Blob for
 * local file:// URIs on React Native (a long-standing RN/Hermes fetch
 * polyfill limitation), which uploaded successfully but left every avatar
 * an empty, unrenderable image.
 */
export async function uploadAvatarImage(userId: string, localUri: string): Promise<string> {
  const client = getSupabaseClientOrNull();
  if (!client) {
    throw new Error("Sign-in isn't available right now.");
  }

  const bytes = await new File(localUri).bytes();
  const path = `${userId}/avatar.jpg`;

  const { error: uploadError } = await client.storage
    .from("avatars")
    .upload(path, bytes, { contentType: "image/jpeg", upsert: true });
  if (uploadError) {
    throw new Error(uploadError.message);
  }

  const { data } = client.storage.from("avatars").getPublicUrl(path);
  // Bust CDN/client-side caching for the (upserted) same path so the new
  // photo shows immediately instead of a stale cached image.
  return `${data.publicUrl}?t=${Date.now()}`;
}
