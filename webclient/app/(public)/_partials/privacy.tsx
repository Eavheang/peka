'use client';

import { Heading } from '@astryxdesign/core/Heading';

export function PublicPrivacy() {
  return (
    <section
      id='privacy'
      aria-labelledby='privacy-title'
      className='grid gap-12 bg-accent px-page py-section text-accent-foreground lg:grid-cols-2 lg:items-end'
    >
      <header className='flex flex-col gap-4'>
        <p className='font-mono text-micro uppercase tracking-label text-accent-foreground'>
          Privacy is a mode, not a slogan
        </p>
        <Heading
          level={2}
          id='privacy-title'
          className='max-w-3xl text-privacy-title font-bold tracking-privacy'
        >
          Your files stay local. You choose where answers run.
        </Heading>
      </header>
      <p className='max-w-md leading-answer lg:justify-self-end'>
        In local mode, retrieval, storage, and inference stay inside your organisation. Cloud mode
        sends only the prompt and retrieved context to your configured endpoint. Peka makes the
        trade-off explicit.
      </p>
    </section>
  );
}
