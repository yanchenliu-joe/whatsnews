import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  getIsPremium,
  identifyPurchaser,
  initPurchases,
  purchasePlan,
  resetPurchaser,
  restorePurchases,
} from "../services/purchases";
import type { PlanId } from "../services/purchases";
import { useAuth } from "./AuthContext";

type SubscriptionState = {
  isPremium: boolean;
  isLoading: boolean;
  purchase: (planId: PlanId) => Promise<boolean>;
  restore: () => Promise<boolean>;
};

const SubscriptionContext = createContext<SubscriptionState>({
  isPremium: false,
  isLoading: true,
  purchase: async () => false,
  restore: async () => false,
});

export function useSubscription() {
  return useContext(SubscriptionContext);
}

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [isPremium, setIsPremium] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  // Tracks whether the initial configure() below has run, and which user id
  // (if any) RevenueCat's identity currently reflects — so the second effect
  // only reacts to real sign-in/sign-out transitions, not the first render.
  const initializedRef = useRef(false);
  const currentPurchaserIdRef = useRef<string | null>(null);

  // Configure RevenueCat once. `user?.id` here reflects whatever the
  // AuthProvider parent already resolved by this first render — non-null
  // only when a persisted session restores synchronously enough to beat this
  // effect; the common case (session restoring async, or auth disabled) is
  // handled by the identity-sync effect below once `user` changes.
  useEffect(() => {
    async function init() {
      try {
        initPurchases(user?.id);
        currentPurchaserIdRef.current = user?.id ?? null;
        const premium = await getIsPremium();
        setIsPremium(premium);
      } catch {
        // non-fatal — default to free
      } finally {
        initializedRef.current = true;
        setIsLoading(false);
      }
    }
    void init();
    // Deliberately runs once on mount only — sign-in/out afterwards is
    // handled by the effect below, which reacts to user?.id changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Link/unlink RevenueCat's identity as the user signs in or out. A no-op
  // until the first effect has configured Purchases, and a no-op when
  // ENABLE_AUTH is off (user stays null forever, so this never fires).
  useEffect(() => {
    if (!initializedRef.current) return;
    const nextUserId = user?.id ?? null;
    if (nextUserId === currentPurchaserIdRef.current) return;

    async function syncPurchaserIdentity() {
      try {
        if (nextUserId) {
          await identifyPurchaser(nextUserId);
        } else {
          await resetPurchaser();
        }
        currentPurchaserIdRef.current = nextUserId;
        const premium = await getIsPremium();
        setIsPremium(premium);
      } catch {
        // non-fatal — keep the previous premium state
      }
    }
    void syncPurchaserIdentity();
  }, [user?.id]);

  const purchase = useCallback(async (planId: PlanId): Promise<boolean> => {
    try {
      await purchasePlan(planId);
      setIsPremium(true);
      return true;
    } catch {
      return false;
    }
  }, []);

  const restore = useCallback(async (): Promise<boolean> => {
    try {
      const hasPremium = await restorePurchases();
      setIsPremium(hasPremium);
      return hasPremium;
    } catch {
      return false;
    }
  }, []);

  return (
    <SubscriptionContext.Provider value={{ isPremium, isLoading, purchase, restore }}>
      {children}
    </SubscriptionContext.Provider>
  );
}
