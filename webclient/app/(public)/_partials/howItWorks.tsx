import clsx from 'clsx';
import { howItWorksSteps } from '@/constants/landing';

export function PublicFlow() {
  return (
    <section
      aria-labelledby='flow-title'
      className='flex flex-col gap-10 border-t border-border px-6 py-25'
    >
      <header className='flex max-w-2xl flex-col gap-4'>
        <p className='font-mono text-xs uppercase tracking-widest text-primary'>One clear path</p>
        <h2 id='flow-title' className='text-5xl md:text-6xl font-bold tracking-tight'>
          From scattered files to a dependable answer.
        </h2>
        <p className='max-w-xl text-lg leading-normal text-muted-foreground'>
          Every step stays visible: what was retrieved, who can see it, and which model generated
          the response.
        </p>
      </header>
      <ol className='grid gap-px border border-border bg-border lg:grid-cols-3'>
        {howItWorksSteps.map((step, index) => (
          <li
            key={step.label}
            className={clsx(
              'flex min-h-64 flex-col justify-between p-6.75',
              index === 0 ? 'bg-foreground text-background' : 'bg-background',
            )}
          >
            <p className='font-mono text-xs text-primary'>
              {String(index + 1).padStart(2, '0')} / {step.label.toUpperCase()}
            </p>
            <article className='flex flex-col gap-2'>
              <h3 className='text-2xl font-semibold tracking-tight'>{step.title}</h3>
              <p
                className={clsx(
                  'max-w-xs text-sm leading-normal',
                  index === 0 ? 'text-background/70' : 'text-muted-foreground',
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
