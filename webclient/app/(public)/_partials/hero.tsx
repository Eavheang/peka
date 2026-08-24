'use client';

import { Heading } from '@astryxdesign/core/Heading';
import { Link as AstryxLink } from '@astryxdesign/core/Link';
import { StatusDot } from '@astryxdesign/core/StatusDot';

export function PublicHero() {
  return (
    <section
      aria-labelledby='hero-title'
      className='mx-auto grid min-h-public-hero w-full items-center gap-hero px-page py-hero lg:grid-cols-2'
    >
      <article className='flex max-w-2xl flex-col gap-5'>
        <p className='font-mono text-micro uppercase tracking-label text-accent'>
          Private knowledge, useful answers
        </p>
        <Heading
          level={1}
          id='hero-title'
          className='max-w-3xl text-hero font-bold tracking-hero text-ink'
        >
          Ask your work.
          <br />
          <em className='font-bold not-italic text-accent'>Keep control.</em>
        </Heading>
        <p className='max-w-xl text-lg leading-copy text-copy'>
          Peka turns your organisation&apos;s documents into a grounded assistant that knows what it
          can access and says when it cannot answer.
        </p>
        <nav aria-label='Landing actions' className='flex flex-wrap gap-3'>
          <AstryxLink
            className='rounded-full border border-accent bg-accent px-4 py-3 text-accent-foreground transition-transform hover:-translate-y-0.5'
            href='/sign-in'
          >
            Start with Peka -&gt;
          </AstryxLink>
          <AstryxLink
            className='rounded-full border border-ink bg-transparent px-4 py-3 transition-transform hover:-translate-y-0.5'
            href='/#how-it-works'
          >
            See the flow
          </AstryxLink>
        </nav>
        <p className='font-mono text-xs text-muted'>
          Local-first retrieval · Role-aware sources · Optional cloud model
        </p>
      </article>

      <article aria-label='Peka chat preview' className='relative'>
        <p className='absolute -top-8 right-0 font-mono text-xs text-muted'>
          A small window into the workspace ↗
        </p>
        <section className='rotate-1 rounded-preview bg-panel p-preview text-panel-foreground shadow-soft'>
          <header className='flex items-center justify-between border-b border-panel-foreground/15 pb-preview'>
            <strong className='tracking-brand'>peka</strong>
            <p className='flex items-center gap-2 font-mono text-micro text-success'>
              <StatusDot variant='success' label='Knowledge base active' />
              KNOWLEDGE BASE ACTIVE
            </p>
          </header>
          <section className='grid min-h-chat md:grid-cols-4'>
            <aside className='hidden border-r border-panel-foreground/15 py-5 pr-4 md:col-span-1 md:block'>
              <p className='mb-4 font-mono text-micro uppercase tracking-widest text-panel-foreground/70'>
                Workspace
              </p>
              <ul className='grid gap-1 text-xs text-panel-foreground/75'>
                <li className='rounded-md bg-panel-foreground/10 px-2.5 py-2 text-panel-foreground'>
                  + New chat
                </li>
                <li className='rounded-md px-2.5 py-2'>Knowledge</li>
                <li className='rounded-md px-2.5 py-2'>Skills</li>
                <li className='rounded-md px-2.5 py-2'>Settings</li>
              </ul>
              <p className='mb-3 mt-7 font-mono text-micro uppercase tracking-widest text-panel-foreground/70'>
                Recent
              </p>
              <ul className='grid gap-2 text-caption text-panel-foreground/75'>
                <li>Q3 planning notes</li>
                <li>Onboarding checklist</li>
              </ul>
            </aside>
            <section className='flex min-h-chat-body flex-col justify-between px-preview py-6 md:col-span-3 md:px-preview-main'>
              <article className='flex flex-col gap-6'>
                <Heading level={2} className='text-chat-heading font-semibold tracking-brand'>
                  What can I find for you?
                </Heading>
                <p className='ml-auto max-w-sm rounded-message bg-panel-foreground/10 px-3.5 py-3 text-xs leading-message text-panel-foreground/80'>
                  What changed in our Q3 launch plan?
                </p>
                <section className='flex max-w-lg flex-col gap-3'>
                  <p className='text-xs leading-answer text-panel-foreground/90'>
                    The launch moved from{' '}
                    <strong className='font-medium text-success'>September 12 to October 3</strong>.
                    The team cited a dependency on the mobile release candidate and a revised
                    partner review.
                  </p>
                  <cite className='w-fit rounded bg-panel-foreground/10 px-2 py-1.5 font-mono text-micro not-italic text-success'>
                    Q3-plan.pdf · p. 4
                  </cite>
                </section>
              </article>
              <p className='rounded-lg border border-panel-foreground/20 px-3 py-3 text-xs text-panel-foreground/60'>
                Ask about your knowledge base ↗
              </p>
            </section>
          </section>
        </section>
      </article>
    </section>
  );
}
