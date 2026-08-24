export default function SignInLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <main className='mx-auto flex w-full max-w-7xl flex-1 items-center justify-center px-4 py-20 sm:px-6 lg:px-8'>
      {children}
    </main>
  );
}
