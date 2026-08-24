'use client';

import { PublicFlow } from '@/app/(public)/_partials/howItWorks';
import { PublicHero } from '@/app/(public)/_partials/hero';
import { PublicPrivacy } from '@/app/(public)/_partials/privacy';

export default function PublicLandingPage() {
  return (
    <main className='w-full overflow-hidden text-ink'>
      <PublicHero />
      <PublicFlow />
      <PublicPrivacy />
    </main>
  );
}
