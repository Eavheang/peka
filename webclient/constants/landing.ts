export const steps = [
  {
    label: 'Ingest',
    title: 'Bring your knowledge in.',
    description: 'Upload local files. Peka indexes them in the background without stopping chat.',
  },
  {
    label: 'Ask',
    title: 'Ask naturally.',
    description:
      "Search happens against the last completed index and respects the user's role before retrieval.",
  },
  {
    label: 'Act',
    title: 'Make something useful.',
    description:
      'Approved skills can turn verified evidence into presentations, documents, and workflows.',
  },
] as const;
