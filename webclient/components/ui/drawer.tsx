"use client";

import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer";

import { cn } from "@/lib/utils";

function Drawer({ ...props }: DrawerPrimitive.Root.Props) {
  return <DrawerPrimitive.Root data-slot="drawer" modal swipeDirection="left" {...props} />;
}

function DrawerClose({ ...props }: DrawerPrimitive.Close.Props) {
  return <DrawerPrimitive.Close data-slot="drawer-close" {...props} />;
}

function DrawerContent({ className, children, ...props }: DrawerPrimitive.Popup.Props) {
  return (
    <DrawerPrimitive.Portal data-slot="drawer-portal">
      <DrawerPrimitive.Backdrop
        data-slot="drawer-overlay"
        className="fixed inset-0 z-50 bg-black/50 opacity-[max(var(--drawer-overlay-min-opacity,0),calc(1-var(--drawer-swipe-progress)))] transition-opacity duration-450 ease-[cubic-bezier(0.32,0.72,0,1)] select-none data-ending-style:pointer-events-none data-ending-style:opacity-0 data-starting-style:opacity-0 data-swiping:duration-0"
      />
      <DrawerPrimitive.Viewport
        data-slot="drawer-viewport"
        data-modal="true"
        className="pointer-events-auto fixed inset-0 z-50 select-none"
      >
        <DrawerPrimitive.Popup
          data-slot="drawer-popup"
          data-swipe-axis="x"
          className={cn(
            "group/drawer-popup pointer-events-auto fixed inset-y-0 left-0 z-50 flex w-(--drawer-content-width) flex-col bg-popover text-sm text-popover-foreground transition-[transform,opacity] duration-450 ease-[cubic-bezier(0.22,1,0.36,1)] will-change-transform outline-none select-none data-[swipe-direction=left]:rounded-r-xl data-[swipe-direction=left]:border-r",
            "[--drawer-content-width:75%] sm:[--drawer-content-width:24rem] data-starting-style:transform-(--closed-transform) data-ending-style:transform-(--closed-transform) data-swiping:duration-0 data-[swipe-direction=left]:[--closed-transform:translate3d(calc(-100%-2px),0,0)] data-[swipe-direction=left]:[--translate-x:var(--drawer-swipe-movement-x)]",
            className,
          )}
          {...props}
        >
          <DrawerPrimitive.Content
            data-slot="drawer-content"
            className="flex min-h-0 flex-1 flex-col overflow-hidden overscroll-contain rounded-[inherit] select-text"
          >
            {children}
          </DrawerPrimitive.Content>
        </DrawerPrimitive.Popup>
      </DrawerPrimitive.Viewport>
    </DrawerPrimitive.Portal>
  );
}

function DrawerTitle({ className, ...props }: DrawerPrimitive.Title.Props) {
  return (
    <DrawerPrimitive.Title
      data-slot="drawer-title"
      className={cn("text-base font-medium text-foreground", className)}
      {...props}
    />
  );
}

export { Drawer, DrawerClose, DrawerContent, DrawerTitle };
