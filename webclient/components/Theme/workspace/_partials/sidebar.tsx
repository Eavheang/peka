"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useState } from "react";
import { ChevronsLeft, ChevronsRight, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import Alertdialog from "@/components/Alertdialog";
import { Drawer, DrawerClose, DrawerContent, DrawerTitle } from "@/components/ui/drawer";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { UserResponse } from "@/interface/auth";
import type { Conversation } from "@/interface/chat";
import { useLogout } from "@/services/auth";
import { useDeleteConversation, useListConversations } from "@/services/chat";
import { endSession, getStoredToken } from "@/utils/auth-storage";
import { ROUTE, Routes } from "@/variables/routes";
import { ConversationHistory } from "./conversationHistory";
import { ProfileMenu } from "./profileMenu";

export function WorkspaceSidebar({
  user,
  collapsed,
  mobileOpen,
  onToggle,
  onMobileOpenChange,
}: {
  user?: UserResponse;
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onMobileOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const logout = useLogout();
  const [logoutOpen, setLogoutOpen] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<Conversation | null>(null);
  const visibleRoutes = Routes.filter((route) => user && route.roles.includes(user.role));
  const conversationsQuery = useListConversations(Boolean(user));
  const deleteConversation = useDeleteConversation();
  const conversations = conversationsQuery.data?.pages.flatMap((page) => page.items);
  const loadMoreConversations = useCallback(() => {
    if (!conversationsQuery.hasNextPage || conversationsQuery.isFetchingNextPage) return;
    void conversationsQuery.fetchNextPage();
  }, [
    conversationsQuery.fetchNextPage,
    conversationsQuery.hasNextPage,
    conversationsQuery.isFetchingNextPage,
  ]);
  const displayName = user?.display_name || user?.email.split("@")[0] || "Workspace";
  const initial = displayName.charAt(0).toUpperCase();

  function handleLogout() {
    const accessToken = getStoredToken("peka_access_token");
    if (!accessToken) {
      endSession();
      return;
    }

    logout.mutate(accessToken, { onSettled: endSession });
  }

  function handleDeleteConversation() {
    if (!conversationToDelete) return;

    const deletedConversationId = conversationToDelete.id;
    deleteConversation.mutate(deletedConversationId, {
      onSuccess: () => {
        setConversationToDelete(null);
        if (pathname === `/workspace/${deletedConversationId}`) router.replace(ROUTE.WORKSPACE);
      },
    });
  }

  return (
    <>
      <aside
        className={`sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-panel text-panel-foreground transition-[width] duration-200 lg:flex ${collapsed ? "w-20" : "w-64"}`}
      >
        <div
          className={`flex h-18.5 items-center border-b border-white/10 px-4 ${collapsed ? "justify-center" : "justify-between"}`}
        >
          {!collapsed && (
            <Link
              aria-label="Peka workspace home"
              className="flex items-center gap-2 text-xl font-bold tracking-tight"
              href={ROUTE.WORKSPACE}
            >
              <Image src="/peka.svg" alt="" aria-hidden="true" width={21} height={21} />
              peka
            </Link>
          )}
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="rounded-md p-2 text-white/60 hover:bg-white/10 hover:text-white"
            onClick={onToggle}
          >
            {collapsed ? (
              <ChevronsRight aria-hidden="true" size={19} />
            ) : (
              <ChevronsLeft aria-hidden="true" size={19} />
            )}
          </button>
        </div>
        <nav
          aria-label="Workspace navigation"
          className="flex min-h-0 flex-1 flex-col gap-1 overflow-hidden px-3 py-5"
        >
          <p
            className={`px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/45 ${collapsed ? "invisible" : ""}`}
          >
            Workspace
          </p>
          {visibleRoutes.map(({ title, path, icon: Icon }) => {
            const isActive = pathname === path;
            const link = (
              <Link
                aria-label={collapsed ? title : undefined}
                key={path}
                title={collapsed ? title : undefined}
                className={`flex h-10 items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors hover:bg-white/10 hover:text-white ${isActive ? "bg-white/10 text-white" : "text-white/65"} ${collapsed ? "mx-auto w-10 flex-none justify-center p-0" : ""}`}
                href={path}
              >
                <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
                {!collapsed && title}
              </Link>
            );

            return collapsed ? (
              <Tooltip key={path}>
                <TooltipTrigger render={link} />
                <TooltipContent side="right">{title}</TooltipContent>
              </Tooltip>
            ) : (
              link
            );
          })}
          {!collapsed && (
            <ConversationHistory
              conversations={conversations}
              error={conversationsQuery.isError && !conversationsQuery.data}
              loading={conversationsQuery.isPending}
              loadingMore={conversationsQuery.isFetchingNextPage}
              hasMore={Boolean(conversationsQuery.hasNextPage)}
              loadMoreError={conversationsQuery.isError && Boolean(conversationsQuery.data)}
              onLoadMore={loadMoreConversations}
              onDelete={setConversationToDelete}
              pathname={pathname}
            />
          )}
        </nav>
        <div className="border-t border-white/10 p-3">
          <ProfileMenu
            collapsed={collapsed}
            displayName={displayName}
            initial={initial}
            onLogout={() => setLogoutOpen(true)}
            role={user?.role}
          />
        </div>
      </aside>
      <Drawer open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <DrawerContent className="!bg-panel !text-panel-foreground w-[min(20rem,85vw)] max-w-[85vw] p-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <DrawerTitle className="flex items-center gap-2 text-xl tracking-tight text-panel-foreground">
              <Image src="/peka.svg" alt="" aria-hidden="true" width={21} height={21} />
              peka
            </DrawerTitle>
            <DrawerClose
              aria-label="Close workspace navigation"
              className="rounded-md p-2 hover:bg-white/10"
            >
              <X aria-hidden="true" size={18} />
            </DrawerClose>
          </div>
          <nav
            aria-label="Mobile workspace navigation"
            className="flex min-h-0 flex-1 flex-col gap-1 overflow-hidden py-5"
          >
            <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-panel-foreground/60">
              Workspace
            </p>
            <div className="grid gap-1">
              {visibleRoutes.map(({ title, path, icon: Icon }) => (
                <Link
                  key={path}
                  className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-panel-foreground/75 hover:bg-white/10 hover:text-panel-foreground"
                  href={path}
                  onClick={() => onMobileOpenChange(false)}
                >
                  <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
                  {title}
                </Link>
              ))}
            </div>
            <ConversationHistory
              conversations={conversations}
              error={conversationsQuery.isError && !conversationsQuery.data}
              loading={conversationsQuery.isPending}
              loadingMore={conversationsQuery.isFetchingNextPage}
              hasMore={Boolean(conversationsQuery.hasNextPage)}
              loadMoreError={conversationsQuery.isError && Boolean(conversationsQuery.data)}
              onLoadMore={loadMoreConversations}
              onDelete={setConversationToDelete}
              onNavigate={() => onMobileOpenChange(false)}
              pathname={pathname}
            />
          </nav>
          <div className="border-t border-white/10 pt-3">
            <ProfileMenu
              displayName={displayName}
              initial={initial}
              onLogout={() => {
                onMobileOpenChange(false);
                setLogoutOpen(true);
              }}
              onNavigate={() => onMobileOpenChange(false)}
              role={user?.role}
            />
          </div>
        </DrawerContent>
      </Drawer>
      <Alertdialog
        open={logoutOpen || Boolean(conversationToDelete)}
        onOpenChange={(open) => {
          if (logoutOpen) {
            setLogoutOpen(open);
            return;
          }
          if (!open) {
            setConversationToDelete(null);
            deleteConversation.reset();
          }
        }}
        title={conversationToDelete ? "Delete conversation?" : "Log out?"}
        description={
          conversationToDelete
            ? deleteConversation.isError
              ? "We could not delete this conversation. Please try again."
              : `Delete “${conversationToDelete.title}”? This cannot be undone.`
            : "End your current workspace session?"
        }
        confirmLabel={conversationToDelete ? "Delete" : "Log out"}
        onConfirm={conversationToDelete ? handleDeleteConversation : handleLogout}
        pending={conversationToDelete ? deleteConversation.isPending : logout.isPending}
      />
    </>
  );
}
