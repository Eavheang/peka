export function PublicPrivacy() {
  return (
    <section
      aria-labelledby='privacy-title'
      className='grid gap-12 bg-primary px-6 py-25 text-primary-foreground lg:grid-cols-2 lg:items-end'
    >
      <header className='flex flex-col gap-4'>
        <p className='font-mono text-xs uppercase tracking-widest text-primary-foreground'>
          Privacy is a mode, not a slogan
        </p>
        <h2 id='privacy-title' className='max-w-3xl text-5xl md:text-7xl font-bold tracking-tight'>
          Your files stay local. You choose where answers run.
        </h2>
      </header>
      <p className='max-w-md leading-relaxed lg:justify-self-end text-primary-foreground'>
        In local mode, retrieval, storage, and inference stay inside your organisation. Cloud mode
        sends only the prompt and retrieved context to your configured endpoint. Peka makes the
        trade-off explicit.
      </p>
    </section>
  );
}
