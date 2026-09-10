// Mobile test infrastructure (added 2026-07-13) — this project had zero
// mobile tests before this. jest-expo is Expo's own Jest preset; it
// extends react-native's preset with mocks for standard Expo SDK modules
// (expo-constants, expo-localization, etc.) so pure utils/hooks that
// import from those don't need manual mocking.
module.exports = {
  preset: "jest-expo",
  transformIgnorePatterns: [
    "node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg)",
  ],
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.d.ts",
  ],
};
