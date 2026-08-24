'use client';

import { TopNav, TopNavItem } from '@astryxdesign/core/TopNav';
import { HStack } from '@astryxdesign/core/HStack';
import { NavIcon } from '@astryxdesign/core/NavIcon';
import { Icon } from '@astryxdesign/core/Icon';
import { Menu } from 'lucide-react';
import Link from 'next/link';

export function PublicNavigation() {
  return (
    <header className='border-b border-line'>
      <TopNav
        aria-label='Primary navigation'
        className='h-nav px-page'
        heading={
          <Link
            aria-label='Peka home'
            className='inline-flex items-center gap-2 text-brand font-bold tracking-brand text-ink'
            href='/'
          >
            <NavIcon icon={<Icon icon={Menu} size='sm' />} />
            peka
          </Link>
        }
        endContent={
          <HStack gap={4}>
            <TopNavItem
              className='hidden text-ink hover:text-accent sm:inline-flex'
              href='/#how-it-works'
              label='How it works'
            />
            <TopNavItem
              className='hidden text-ink hover:text-accent sm:inline-flex'
              href='/#privacy'
              label='Privacy'
            />
            <TopNavItem
              className='rounded-full bg-ink px-3.5 py-2 text-paper transition-transform hover:-translate-y-0.5'
              href='/sign-in'
              label='Open workspace'
            />
          </HStack>
        }
      />
    </header>
  );
}
