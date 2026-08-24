import PublicLayout from '@/components/themes/public/layout';

export default function Layout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <PublicLayout>{children}</PublicLayout>;
}
