declare module "bun:test" {
  export function test(name: string, fn: () => void | Promise<void>): void;
  export function expect(actual: unknown): {
    toBe(expected: unknown): void;
    toContain(expected: string): void;
    toEqual(expected: unknown): void;
  };
}
