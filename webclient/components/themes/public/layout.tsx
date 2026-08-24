import type { ReactNode } from 'react';

import { PublicFooter } from './_partials/Footer';
import { PublicNavigation } from './_partials/Navigation';

export default function PublicLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <>
      <PublicNavigation />
      {children}
      <PublicFooter />
    </>
  );
}
