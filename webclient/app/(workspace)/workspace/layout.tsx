import WorkspaceLayout from "@/components/Theme/workspace/layout";

export default function Layout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <WorkspaceLayout>{children}</WorkspaceLayout>;
}
