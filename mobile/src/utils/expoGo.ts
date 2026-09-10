import Constants, { ExecutionEnvironment } from "expo-constants";

/** True when running inside the Expo Go client, where custom native modules aren't linked. */
export const IS_EXPO_GO = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
