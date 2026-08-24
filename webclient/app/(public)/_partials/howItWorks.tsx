'use client';

import { Heading } from '@astryxdesign/core/Heading';
import clsx from 'clsx';
import { steps } from '@/constants/landing';

export function PublicFlow() {
  return (
    <section
      id='how-it-works'
      aria-labelledby='flow-title'
      className='flex flex-col gap-flow-header border-t border-line px-page py-section'
    >
      <header className='flex max-w-2xl flex-col gap-4'>
        <p className='font-mono text-micro uppercase tracking-label text-accent'>One clear path</p>
        <Heading level={2} id='flow-title' className='text-flow-title font-bold tracking-section'>
          From scattered files to a dependable answer.
        </Heading>
        <p className='max-w-xl text-lg leading-copy text-copy-secondary'>
          Every step stays visible: what was retrieved, who can see it, and which model generated
          the response.
        </p>
      </header>
      <ol className='grid gap-px border border-line bg-line lg:grid-cols-3'>
        {steps.map((step, index) => (
          <li
            key={step.label}
            className={clsx(
              'flex min-h-64 flex-col justify-between p-card',
              index === 0 ? 'bg-ink text-paper' : 'bg-paper',
            )}
          >
            <p className='font-mono text-xs text-accent'>
              {String(index + 1).padStart(2, '0')} / {step.label.toUpperCase()}
            </p>
            <article className='flex flex-col gap-2'>
              <Heading level={3} className='text-step-title font-semibold tracking-brand'>
                {step.title}
              </Heading>
              <p
                className={clsx(
                  'max-w-xs text-sm leading-step',
                  index === 0 ? 'text-paper/70' : 'text-copy-tertiary',
                )}
              >
                {step.description}
              </p>
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}
