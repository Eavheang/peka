'use client';

import * as React from 'react';
import { Progress as ProgressPrimitive } from '@base-ui/react/progress';

import { cn } from '@/lib/utils';

function Progress({ className, ...props }: ProgressPrimitive.Root.Props) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn('relative h-2 w-full overflow-hidden rounded-full bg-secondary', className)}
      {...props}
    >
      <ProgressPrimitive.Track className="h-full w-full">
        <ProgressPrimitive.Indicator className="h-full w-full bg-primary transition-transform" />
      </ProgressPrimitive.Track>
    </ProgressPrimitive.Root>
  );
}

export { Progress };
