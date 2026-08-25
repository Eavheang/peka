import type { ReactNode } from 'react';

export const STEPS: {
  tag: string;
  title: ReactNode;
  description: string;
  cta: boolean;
  query: string;
  response: ReactNode;
  citation: string;
  activeTab: string;
}[] = [
  {
    tag: 'Private knowledge, useful answers',
    title: (
      <>
        Ask your work.
        <br />
        <span className='text-primary'>Keep control.</span>
      </>
    ),
    description:
      'Peka turns your organisation’s documents into a grounded assistant that knows what it can access and says when it cannot answer.',
    cta: true,
    query: 'What changed in our Q3 launch plan?',
    response: (
      <>
        The launch moved from{' '}
        <strong className='font-medium text-success'>September 12 to October 3</strong>. The team
        cited a dependency on the mobile release candidate.
      </>
    ),
    citation: 'Q3-plan.pdf · p. 4',
    activeTab: '+ New chat',
  },
  {
    tag: 'Role-Aware Permissions',
    title: (
      <>
        Respect privacy <br />
        <span className='text-primary'>by default.</span>
      </>
    ),
    description:
      'Documents inherit existing enterprise access rules. Users only receive context from files they have direct authorization to read.',
    cta: false,
    query: 'Can you summarize executive salary metrics?',
    response: (
      <>
        <span className='font-medium text-danger'>Access restricted:</span> Your current role does
        not have read permissions for HR & Legal repositories.
      </>
    ),
    citation: 'Security policy · Access Log #802',
    activeTab: 'Knowledge',
  },
  {
    tag: 'Zero Data Leakage',
    title: (
      <>
        Local retrieval, <br />
        <span className='text-primary'>your terms.</span>
      </>
    ),
    description:
      'Embed and process your files on your hardware. Optionally route complex requests to private cloud models without surrendering raw documents.',
    cta: false,
    query: 'Extract key API keys and tokens from codebase.',
    response: (
      <>
        Indexed <strong className='font-medium text-success'>1,420 files locally</strong>.
        Processing performed entirely on-device via local vector store.
      </>
    ),
    citation: 'local-index.db · 0.4ms latency',
    activeTab: 'Settings',
  },
];

export const WORKSPACE_TABS = ['+ New chat', 'Knowledge', 'Skills', 'Settings'];

export const howItWorksSteps = [
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
