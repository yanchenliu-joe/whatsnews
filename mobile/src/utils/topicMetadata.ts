/**
 * Icon + one-line description per topic, for ManageTopicsScreen's
 * icon/description row style (2026-07-11 design pass, matching the
 * reference mockup). Kept as its own file rather than extending
 * ALL_TOPICS in topicsList.ts, which is a plain string[] consumed
 * elsewhere (OnboardingScreen's topic picker) — changing its shape would
 * have meant updating every consumer for a feature only this screen needs.
 *
 * English-only, not run through i18n — same precedent as
 * getTopicDisplayName.ts's shorthand names (topic *names* are already
 * untranslated regardless of UI language; see docs/ENGINEERING.md's Mobile
 * Switching Pattern), extended here to descriptions for consistency.
 */

export type TopicMeta = {
  icon: string;
  description: string;
};

export const TOPIC_METADATA: Record<string, TopicMeta> = {
  "Artificial Intelligence": { icon: "🤖", description: "Models, research, and product launches" },
  Technology: { icon: "💻", description: "Gadgets, software, and the tech industry" },
  Markets: { icon: "📈", description: "Stocks, crypto, economy, and finance" },
  Politics: { icon: "🏛️", description: "Policy, elections, and government" },
  Geopolitics: { icon: "🌍", description: "Global affairs and international relations" },
  "Climate Change": { icon: "🌱", description: "Climate, energy, and sustainability" },
  Healthcare: { icon: "❤️", description: "Health, wellness, and medical news" },
  Business: { icon: "💼", description: "Companies, startups, and leadership" },
  Cybersecurity: { icon: "🔒", description: "Breaches, threats, and digital security" },
  Science: { icon: "🧪", description: "Discoveries, research, and innovation" },
  Energy: { icon: "⚡", description: "Oil, renewables, and power markets" },
  Defense: { icon: "🛡️", description: "Military, weapons, and national security" },
  Space: { icon: "🚀", description: "Launches, exploration, and astronomy" },
  Crypto: { icon: "₿", description: "Bitcoin, blockchain, and digital assets" },
  Sports: { icon: "⚽", description: "Scores, news, and highlights" },
  Entertainment: { icon: "🎬", description: "Movies, TV, and celebrity news" },
  Labor: { icon: "👷", description: "Jobs, unions, and the workforce" },
  "Real Estate": { icon: "🏠", description: "Housing, property, and development" },
  Education: { icon: "🎓", description: "Schools, universities, and learning" },
  Transportation: { icon: "🚆", description: "Cars, transit, and infrastructure" },
};

const FALLBACK_META: TopicMeta = { icon: "📰", description: "" };

export function getTopicMeta(topicName: string): TopicMeta {
  return TOPIC_METADATA[topicName] ?? FALLBACK_META;
}
