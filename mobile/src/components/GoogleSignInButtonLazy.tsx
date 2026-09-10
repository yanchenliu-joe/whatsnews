import type { StyleProp, ViewStyle } from "react-native";
import { Image, StyleSheet, Text, TouchableOpacity } from "react-native";
import { useTranslation } from "react-i18next";
import { isGoogleSignInAvailable } from "../services/socialAuth";
import { GOOGLE_G_LOGO_URI } from "../assets/googleGLogo";
import { colors } from "../theme";

/**
 * @react-native-google-signin's native GoogleSigninButton renders Google's
 * own fixed "Sign in with Google" text (not customizable, unlike Apple's
 * AppleAuthenticationButton, which offers a CONTINUE buttonType). To show
 * "Continue with Google" — matching Apple's CONTINUE button — this renders
 * a plain custom button instead of the native component. Google's brand
 * guidelines permit custom buttons (unlike Apple's App Store Review
 * Guidelines, which mandate the native Apple button); only the native
 * signIn() call itself needs the native module, not the button chrome.
 *
 * @react-native-google-signin still binds to a native module the instant
 * it's imported and crashes in Expo Go (unlike Apple's SDK, which degrades
 * gracefully) — see isGoogleSignInAvailable() in socialAuth.ts. This
 * wrapper still checks availability before rendering, so the feature stays
 * hidden (not broken) in Expo Go.
 *
 * Shared between AccountScreen and OnboardingScreen — do not copy this
 * pattern inline elsewhere; import from here so the one safety check stays
 * in one place (see docs/ENGINEERING.md).
 */
export default function GoogleSignInButtonLazy({
  onPress,
  disabled,
  style,
}: {
  onPress: () => void;
  disabled: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useTranslation();
  if (!isGoogleSignInAvailable()) return null;
  return (
    <TouchableOpacity
      style={[styles.button, style]}
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.8}
    >
      <Image source={{ uri: GOOGLE_G_LOGO_URI }} style={styles.gLogo} resizeMode="contain" />
      <Text style={styles.label}>{t("signIn.continueWithGoogle")}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
  },
  gLogo: {
    width: 20,
    height: 20,
    marginRight: 10,
  },
  // fontWeight/fontSize matched to AppleAuthenticationButton's rendered
  // label (SF Pro Semibold ~17pt) so the two buttons read as a pair.
  label: {
    fontSize: 17,
    fontWeight: "600",
    color: colors.ink,
  },
});
