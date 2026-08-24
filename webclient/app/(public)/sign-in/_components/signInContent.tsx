import { Heading } from '@astryxdesign/core/Heading';
import { Link as AstryxLink } from '@astryxdesign/core/Link';

export function SignInContent() {
  return (
    <section
      aria-labelledby='sign-in-title'
      className='flex w-full max-w-md flex-col gap-4 rounded-card border border-line bg-paper-muted p-8'
    >
      <p className='font-mono text-micro uppercase tracking-label text-accent'>Workspace access</p>
      <Heading level={1} id='sign-in-title' className='text-4xl font-bold tracking-tight'>
        Sign in to Peka.
      </Heading>
      <p className='text-muted'>
        Authentication is not configured in this deployment yet. Return to landing page for product
        overview.
      </p>
      <AstryxLink
        className='w-fit rounded-full bg-accent px-5 py-3 font-medium text-accent-foreground transition-transform hover:-translate-y-0.5'
        href='/'
      >
        Back to Peka
      </AstryxLink>
    </section>
  );
}
