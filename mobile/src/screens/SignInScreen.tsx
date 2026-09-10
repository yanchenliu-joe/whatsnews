import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useTranslation } from "react-i18next";
import {
  AppleAuthenticationButton,
  AppleAuthenticationButtonStyle,
  AppleAuthenticationButtonType,
} from "expo-apple-authentication";
import { useAuth } from "../context/AuthContext";
import { isAppleSignInAvailable } from "../services/socialAuth";
import GoogleSignInButtonLazy from "../components/GoogleSignInButtonLazy";
import { validateEmailPassword } from "../utils/authErrors";
import type { RootStackParamList } from "../navigation/types";
import { colors } from "../theme";
import { isRTL } from "../utils/rtl";

type Props = NativeStackScreenProps<RootStackParamList, "SignIn">;
type AuthMode = "sign_in" | "sign_up";

/**
 * Dedicated Sign In / Sign Up screen (Phase 36, added 2026-07-06) — extracted
 * out of AccountScreen.tsx, which used to embed this form inline. Presented
 * as a modal (same convention as PaywallScreen). Self-contained: does not
 * share a component with OnboardingScreen.tsx's AuthStep, which stays
 * untouched — see docs/ENGINEERING.md's Authentication section, "Known duplication, not
 * yet consolidated," for why that duplication was previously left alone;
 * same reasoning applies here (focused modifications, no regression risk to
 * a working, already-shipped onboarding flow).
 */
export default function SignInScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const {
    authEnabled,
    authBusy,
    signInWithEmail,
    signUpWithEmail,
    signInWithApple,
    signInWithGoogle,
  } = useAuth();

  const [mode, setMode] = useState<AuthMode>("sign_in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [appleAvailable, setAppleAvailable] = useState(false);

  useEffect(() => {
    void isAppleSignInAvailable().then(setAppleAvailable);
  }, []);

  function handleSuccess() {
    navigation.goBack();
  }

  async function handleAppleSignIn() {
    setFormError(null);
    setFormMessage(null);
    const result = await signInWithApple();
    if (!result.ok) {
      if (result.message) setFormError(result.message);
      return;
    }
    handleSuccess();
  }

  async function handleGoogleSignIn() {
    setFormError(null);
    setFormMessage(null);
    const result = await signInWithGoogle();
    if (!result.ok) {
      if (result.message) setFormError(result.message);
      return;
    }
    handleSuccess();
  }

  function switchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setFormError(null);
    setFormMessage(null);
    setConfirmPassword("");
  }

  async function handleSubmit() {
    setFormError(null);
    setFormMessage(null);
    const validationError = validateEmailPassword(
      email,
      password,
      mode === "sign_up" ? confirmPassword : undefined,
    );
    if (validationError) {
      setFormError(validationError);
      return;
    }
    const result =
      mode === "sign_up"
        ? await signUpWithEmail(email, password)
        : await signInWithEmail(email, password);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    if (result.message) {
      // e.g. "check your email to confirm" — no active session yet, stay on the form
      setFormMessage(result.message);
      setPassword("");
      setConfirmPassword("");
      setMode("sign_in");
      return;
    }
    handleSuccess();
  }

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      <TouchableOpacity
        style={[styles.closeBtn, isRTL() && styles.closeBtnRTL]}
        onPress={() => navigation.goBack()}
        activeOpacity={0.7}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.eyebrow}>WHATSNEWS</Text>
        <Text style={styles.headline}>
          {mode === "sign_in" ? t("signIn.welcomeBack") : t("signIn.createAccount")}
        </Text>
        <Text style={styles.sub}>{t("signIn.subDefault")}</Text>

        {!authEnabled ? (
          <Text style={styles.mutedText}>{t("signIn.unavailable")}</Text>
        ) : (
          <>
            {appleAvailable ? (
              <AppleAuthenticationButton
                buttonType={AppleAuthenticationButtonType.CONTINUE}
                buttonStyle={AppleAuthenticationButtonStyle.BLACK}
                cornerRadius={10}
                style={styles.socialBtn}
                onPress={() => void handleAppleSignIn()}
              />
            ) : null}
            <GoogleSignInButtonLazy
              onPress={() => void handleGoogleSignIn()}
              disabled={authBusy}
              style={styles.socialBtn}
            />

            <View style={styles.dividerRow}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerLabel}>{t("signIn.orContinueWithEmail")}</Text>
              <View style={styles.dividerLine} />
            </View>

            <View style={styles.chipRow}>
              {(["sign_in", "sign_up"] as AuthMode[]).map((m) => (
                <TouchableOpacity
                  key={m}
                  onPress={() => switchMode(m)}
                  activeOpacity={0.7}
                  style={[styles.chip, mode === m && styles.chipActive]}
                >
                  <Text style={[styles.chipLabel, mode === m && styles.chipLabelActive]}>
                    {m === "sign_in" ? t("signIn.signIn") : t("signIn.signUp")}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
              placeholder={t("signIn.email")}
              placeholderTextColor={colors.muted}
              editable={!authBusy}
            />
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              textContentType={mode === "sign_up" ? "newPassword" : "password"}
              placeholder={t("signIn.password")}
              placeholderTextColor={colors.muted}
              editable={!authBusy}
            />
            {mode === "sign_up" ? (
              <TextInput
                style={styles.input}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
                textContentType="newPassword"
                placeholder={t("signIn.confirmPassword")}
                placeholderTextColor={colors.muted}
                editable={!authBusy}
              />
            ) : null}

            {formError ? <Text style={styles.errorText}>{formError}</Text> : null}
            {formMessage ? <Text style={styles.successText}>{formMessage}</Text> : null}

            <TouchableOpacity
              onPress={() => void handleSubmit()}
              activeOpacity={0.7}
              style={styles.primaryBtn}
              disabled={authBusy}
            >
              {authBusy ? (
                <ActivityIndicator color={colors.white} />
              ) : (
                <Text style={styles.primaryBtnLabel}>
                  {mode === "sign_up" ? t("signIn.createAccountBtn") : t("signIn.signIn")}
                </Text>
              )}
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  closeBtn: {
    position: "absolute",
    top: 56,
    right: 20,
    zIndex: 10,
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  closeBtnRTL: { right: undefined, left: 20 },
  closeText: { fontSize: 16, color: colors.muted },
  scroll: { flex: 1 },
  content: { paddingHorizontal: 28, paddingTop: 56, paddingBottom: 40 },

  eyebrow: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: 8,
  },
  headline: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.5,
    marginBottom: 10,
  },
  sub: {
    fontSize: 15,
    color: colors.summary,
    lineHeight: 21,
    marginBottom: 28,
  },
  mutedText: { fontSize: 14, color: colors.muted, lineHeight: 20 },

  socialBtn: { width: "100%", height: 48, marginBottom: 10 },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginVertical: 16,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: colors.border },
  dividerLabel: { fontSize: 12, color: colors.muted },

  chipRow: { flexDirection: "row", gap: 8, marginBottom: 16 },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 18,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
  },
  chipActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  chipLabel: { fontSize: 13, fontWeight: "600", color: colors.muted },
  chipLabelActive: { color: colors.white },

  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.ink,
    marginBottom: 12,
  },
  primaryBtn: {
    marginTop: 4,
    backgroundColor: colors.ink,
    borderRadius: 6,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  primaryBtnLabel: { fontSize: 15, fontWeight: "700", color: colors.white },
  errorText: { fontSize: 13, lineHeight: 18, color: colors.danger, marginBottom: 10 },
  successText: { fontSize: 13, lineHeight: 18, color: colors.success, marginBottom: 10 },
});
