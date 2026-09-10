import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";

import { useAuth } from "../context/AuthContext";
import { useProfile } from "../hooks/useProfile";
import { updateAvatarUrl } from "../services/avatarApi";
import { uploadAvatarImage } from "../utils/avatarUpload";
import AnchoredMenu from "./AnchoredMenu";
import type { AppNavigationProp } from "../navigation/types";
import { colors } from "../theme";

const SIZE = 72;

/**
 * Avatar circle at the top of AccountScreen (Phase 37, added 2026-07-06).
 * Guest: tap -> SignIn. Signed in: tap -> action sheet -> camera/library ->
 * upload directly to Supabase Storage (uploadAvatarImage) -> PATCH
 * /me/avatar -> refetch profile. New native module (expo-image-picker) —
 * needs an EAS dev build, won't work in Expo Go (same constraint as the
 * OAuth native sign-in buttons and the zeego article-tools menu).
 *
 * avatarUrl auto-populates from Google's own account photo on Google
 * sign-in (see AuthContext.tsx's signInWithSocialIdToken) or from a manual
 * upload here — never from Apple, which has no photo field at all. With no
 * avatar at all (guest, Apple sign-in, or a Google account with no photo),
 * this renders a plain gray "+" rather than a text-initial placeholder.
 */
export default function AvatarPicker() {
  const navigation = useNavigation<AppNavigationProp>();
  const { t } = useTranslation();
  const { authStatus, session, user } = useAuth();
  const { avatarUrl, refetch } = useProfile();
  const [uploading, setUploading] = useState(false);

  const isSignedIn = authStatus === "signed_in";

  async function pickAndUpload(source: "camera" | "library") {
    const accessToken = session?.access_token;
    if (!user || !accessToken) return;

    const permission =
      source === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        t("avatarPicker.permissionNeededTitle"),
        source === "camera"
          ? t("avatarPicker.cameraPermissionMessage")
          : t("avatarPicker.libraryPermissionMessage"),
      );
      return;
    }

    const result =
      source === "camera"
        ? await ImagePicker.launchCameraAsync({ allowsEditing: true, aspect: [1, 1], quality: 0.8 })
        : await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ["images"],
            allowsEditing: true,
            aspect: [1, 1],
            quality: 0.8,
          });
    if (result.canceled || !result.assets?.[0]) return;

    setUploading(true);
    try {
      const publicUrl = await uploadAvatarImage(user.id, result.assets[0].uri);
      await updateAvatarUrl(accessToken, publicUrl);
      await refetch();
    } catch (error) {
      Alert.alert(
        t("avatarPicker.updateFailedTitle"),
        error instanceof Error ? error.message : t("avatarPicker.updateFailedMessage"),
      );
    } finally {
      setUploading(false);
    }
  }

  const circle = (
    <View style={[styles.circle, !avatarUrl && !uploading ? styles.circleEmpty : null]}>
      {uploading ? (
        <ActivityIndicator color={colors.white} size="small" />
      ) : avatarUrl ? (
        <Image source={{ uri: avatarUrl }} style={styles.image} cachePolicy="memory-disk" />
      ) : (
        <Text style={styles.plusIcon}>+</Text>
      )}
    </View>
  );

  if (!isSignedIn) {
    return (
      <TouchableOpacity
        onPress={() => navigation.navigate("SignIn")}
        activeOpacity={0.8}
        style={styles.wrap}
      >
        {circle}
      </TouchableOpacity>
    );
  }

  const sourceMenuItems = [
    { key: "camera", label: t("avatarPicker.takePhoto"), onSelect: () => void pickAndUpload("camera") },
    { key: "library", label: t("avatarPicker.chooseFromLibrary"), onSelect: () => void pickAndUpload("library") },
  ];

  return (
    <AnchoredMenu items={sourceMenuItems} triggerStyle={[styles.wrap, styles.triggerClip]}>
      <TouchableOpacity activeOpacity={0.8} disabled={uploading}>
        {circle}
      </TouchableOpacity>
    </AnchoredMenu>
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: "flex-start" },
  // Matches circle's own corner radius — passed to AnchoredMenu's
  // triggerStyle (2026-07-12 fix), which routes it through
  // <DropdownMenu.Trigger style={...}>. zeego's <Trigger asChild> always
  // does cloneElement(children, { style, ...}) using ITS OWN style prop,
  // unconditionally overwriting whatever style the child (the
  // TouchableOpacity) had directly on its own JSX — so this can't just be
  // set on the TouchableOpacity itself. See AnchoredMenu.tsx.
  triggerClip: { width: SIZE, height: SIZE, borderRadius: SIZE / 2, overflow: "hidden" },
  circle: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  circleEmpty: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  image: { width: SIZE, height: SIZE },
  plusIcon: { fontSize: 32, fontWeight: "300", color: colors.faint },
});
