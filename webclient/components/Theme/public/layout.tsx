import type { ReactNode } from 'react';

import { PublicFooter } from './Footer';
import { PublicNavigation } from './Navigation';

export default function PublicLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <>
      <PublicNavigation />
      {children}
      <PublicFooter />
    </>
  );
}
