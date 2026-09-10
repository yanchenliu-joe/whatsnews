const TOPIC_DISPLAY_NAMES: Record<string, string> = {
  // Original 10
  "Artificial Intelligence": "AI",
  "Climate Change": "Climate",
  Technology: "Tech",
  Markets: "Markets",
  Geopolitics: "Geo",
  Healthcare: "Health",
  Energy: "Energy",
  Cybersecurity: "Cyber",
  Business: "Business",
  Defense: "Defense",

  // New 10 (Phase 19)
  Science: "Science",
  Crypto: "Crypto",
  "Real Estate": "Real Estate",
  Politics: "Politics",
  Space: "Space",
  Education: "Education",
  Labor: "Labor",
  Sports: "Sports",
  Entertainment: "Film & TV",
  Transportation: "Transit",
};

export function getTopicDisplayName(topicName: string): string {
  return TOPIC_DISPLAY_NAMES[topicName] ?? topicName;
}
