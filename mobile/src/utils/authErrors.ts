/** Map Supabase auth errors to user-friendly messages (no secrets). */

type AuthErrorLike = {
  message?: string;
  status?: number;
};

export function friendlyAuthError(error: unknown): string {
  if (!error || typeof error !== "object") {
    return "Something went wrong. Please try again.";
  }

  const authError = error as AuthErrorLike;
  const message = authError.message?.toLowerCase() ?? "";

  if (message.includes("invalid login credentials")) {
    return "Incorrect email or password.";
  }
  if (message.includes("email not confirmed")) {
    return "Please confirm your email before signing in.";
  }
  if (message.includes("user already registered")) {
    return "An account with this email already exists. Try signing in.";
  }
  if (message.includes("password") && message.includes("short")) {
    return "Password is too short. Use at least 6 characters.";
  }
  if (message.includes("valid email")) {
    return "Enter a valid email address.";
  }
  if (message.includes("rate limit") || authError.status === 429) {
    return "Too many attempts. Wait a moment and try again.";
  }
  if (message.includes("network") || message.includes("fetch")) {
    return "Network error. Check your connection and try again.";
  }

  if (authError.message) {
    return authError.message;
  }

  return "Something went wrong. Please try again.";
}

export function validateEmailPassword(
  email: string,
  password: string,
  confirmPassword?: string,
): string | null {
  const trimmedEmail = email.trim();
  if (!trimmedEmail) {
    return "Email is required.";
  }
  if (!trimmedEmail.includes("@")) {
    return "Enter a valid email address.";
  }
  if (!password) {
    return "Password is required.";
  }
  if (password.length < 6) {
    return "Password must be at least 6 characters.";
  }
  if (confirmPassword !== undefined && password !== confirmPassword) {
    return "Passwords do not match.";
  }
  return null;
}
